"""
routers/animals.py
Endpoints for the Animal Edit page (AnimalEdit.jsx)

Mount in main.py:
    from routers import animals
    app.include_router(animals.router)   # prefix: /api/animals
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from auth import get_current_user

router = APIRouter(prefix="/api/animals", tags=["animals"])


# ─── helpers ─────────────────────────────────────────────────────────────────

def _row(r):
    """Convert a SQLAlchemy Row to a plain dict."""
    return dict(r._mapping) if r else {}


def _nullable_int(v):
    try:
        return int(v) if v not in (None, "", "None") else None
    except Exception:
        return None


def _nullable_float(v):
    try:
        return float(v) if v not in (None, "", "None") else None
    except Exception:
        return None


# ─── GET animal basics ────────────────────────────────────────────────────────

@router.get("/{animal_id}")
def get_animal(animal_id: int, db: Session = Depends(get_db),
               current_user=Depends(get_current_user)):
    row = db.execute(text("""
        SELECT a.*, c.Color1, c.Color2, c.Color3, c.Color4, c.Color5
        FROM Animals a
        LEFT JOIN Colors c ON c.AnimalID = a.AnimalID
        WHERE a.AnimalID = :aid
    """), {"aid": animal_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Animal not found")
    return _row(row)


# ─── GET species breeds ───────────────────────────────────────────────────────

@router.get("/species/{species_id}/breeds")
def get_breeds(species_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT BreedLookupID AS id, Breed AS name
        FROM SpeciesBreedLookupTable
        WHERE SpeciesID = :sid AND (breedavailable = 1 OR breedavailable IS NULL)
        ORDER BY Breed
    """), {"sid": species_id}).fetchall()
    return [_row(r) for r in rows]


# ─── GET species categories ───────────────────────────────────────────────────

@router.get("/species/{species_id}/categories")
def get_categories(species_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT SpeciesCategoryID AS id, SpeciesCategory AS name
        FROM speciescategory
        WHERE SpeciesID = :sid
        ORDER BY SpeciesCategoryOrder, SpeciesCategory
    """), {"sid": species_id}).fetchall()
    return [_row(r) for r in rows]


# ─── GET registrations ────────────────────────────────────────────────────────

@router.get("/{animal_id}/registrations")
def get_registrations(animal_id: int, db: Session = Depends(get_db),
                       current_user=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT AnimalRegistrationID, RegType, RegNumber
        FROM animalregistration
        WHERE AnimalID = :aid
        ORDER BY RegType
    """), {"aid": animal_id}).fetchall()
    return [_row(r) for r in rows]


# ─── POST update basics ───────────────────────────────────────────────────────

@router.post("/{animal_id}/update-basics")
async def update_basics(animal_id: int, request: Request,
                         db: Session = Depends(get_db),
                         current_user=Depends(get_current_user)):
    form = await request.form()
    f = lambda k: form.get(k) or None
    n = lambda k: _nullable_float(form.get(k))
    i = lambda k: _nullable_int(form.get(k))

    db.execute(text("""
        UPDATE Animals SET
            FullName          = :name,
            Category          = :category,
            DOBDay            = :dob_day,
            DOBMonth          = :dob_month,
            DOBYear           = :dob_year,
            BreedID           = :breed1,
            BreedID2          = :breed2,
            BreedID3          = :breed3,
            BreedID4          = :breed4,
            Height            = :height,
            Weight            = :weight,
            Gaited            = :gaited,
            Warmblood         = :warmblood,
            Horns             = :horns,
            Temperment        = :temperament,
            Vaccinations      = :vaccinations,
            AncestryDescription = :ancestry_desc
        WHERE AnimalID = :aid
    """), {
        "aid": animal_id,
        "name": f("Name"),
        "category": f("Category"),
        "dob_day": i("DOBDay"), "dob_month": i("DOBMonth"), "dob_year": i("DOBYear"),
        "breed1": i("BreedID"), "breed2": i("BreedID2"),
        "breed3": i("BreedID3"), "breed4": i("BreedID4"),
        "height": n("Height"), "weight": n("Weight"),
        "gaited": f("Gaited"), "warmblood": f("Warmblood"),
        "horns": f("Horns"), "temperament": i("Temperment"),
        "vaccinations": f("Vaccinations"),
        "ancestry_desc": f("AncestryDescription"),
    })

    # Update colors (separate Colors table)
    existing = db.execute(text("SELECT COUNT(*) FROM Colors WHERE AnimalID = :aid"), {"aid": animal_id}).scalar()
    color_params = {
        "aid": animal_id,
        "c1": f("Color1"), "c2": f("Color2"), "c3": f("Color3"),
        "c4": f("Color4"), "c5": f("Color5"),
    }
    if existing:
        db.execute(text("""
            UPDATE Colors SET Color1=:c1, Color2=:c2, Color3=:c3, Color4=:c4, Color5=:c5
            WHERE AnimalID=:aid
        """), color_params)
    else:
        db.execute(text("""
            INSERT INTO Colors (AnimalID, Color1, Color2, Color3, Color4, Color5)
            VALUES (:aid, :c1, :c2, :c3, :c4, :c5)
        """), color_params)

    db.commit()
    return {"message": "Basics updated"}


# ─── GET pricing ──────────────────────────────────────────────────────────────

@router.get("/{animal_id}/pricing")
def get_pricing(animal_id: int, db: Session = Depends(get_db),
                current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT * FROM Pricing WHERE AnimalID = :aid"), {"aid": animal_id}).fetchone()
    if not row:
        # Auto-create pricing row
        db.execute(text("INSERT INTO Pricing (AnimalID) VALUES (:aid)"), {"aid": animal_id})
        db.commit()
        row = db.execute(text("SELECT * FROM Pricing WHERE AnimalID = :aid"), {"aid": animal_id}).fetchone()
    return _row(row)


# ─── POST update pricing ──────────────────────────────────────────────────────

@router.post("/{animal_id}/update-pricing")
async def update_pricing(animal_id: int, request: Request,
                          db: Session = Depends(get_db),
                          current_user=Depends(get_current_user)):
    form = await request.form()
    f = lambda k: form.get(k) or None
    n = lambda k: _nullable_float(form.get(k))

    for_sale = 1 if form.get("ForSale") in ("1", "Yes", "True") else 0
    sold     = 1 if form.get("Sold")    in ("1", "Yes", "True") else 0
    free     = 1 if form.get("Free")    in ("1", "Yes", "True") else 0

    existing = db.execute(text("SELECT COUNT(*) FROM Pricing WHERE AnimalID = :aid"), {"aid": animal_id}).scalar()
    params = {
        "aid": animal_id,
        "for_sale": for_sale, "sold": sold, "free": free,
        "price": n("Price"), "stud_fee": n("StudFee"),
        "embryo_price": n("EmbryoPrice"), "semen_price": n("SemenPrice"),
        "price_comments": f("PriceComments"),
        "finance_terms": f("Financeterms"),
    }
    if existing:
        db.execute(text("""
            UPDATE Pricing SET
                ForSale=:for_sale, Sold=:sold, Free=:free,
                Price=:price, StudFee=:stud_fee,
                EmbryoPrice=:embryo_price, SemenPrice=:semen_price,
                PriceComments=:price_comments, Financeterms=:finance_terms
            WHERE AnimalID=:aid
        """), params)
    else:
        db.execute(text("""
            INSERT INTO Pricing (AnimalID, ForSale, Sold, Free, Price, StudFee,
                EmbryoPrice, SemenPrice, PriceComments, Financeterms)
            VALUES (:aid, :for_sale, :sold, :free, :price, :stud_fee,
                :embryo_price, :semen_price, :price_comments, :finance_terms)
        """), params)

    # Update co-owners on Animals table
    db.execute(text("""
        UPDATE Animals SET
            CoOwnerName1=:n1, CoOwnerLink1=:l1, CoOwnerBusiness1=:b1,
            CoOwnerName2=:n2, CoOwnerLink2=:l2, CoOwnerBusiness2=:b2,
            CoOwnerName3=:n3, CoOwnerLink3=:l3, CoOwnerBusiness3=:b3
        WHERE AnimalID=:aid
    """), {
        "aid": animal_id,
        "n1": f("CoOwnerName1"), "l1": f("CoOwnerLink1"), "b1": f("CoOwnerBusiness1"),
        "n2": f("CoOwnerName2"), "l2": f("CoOwnerLink2"), "b2": f("CoOwnerBusiness2"),
        "n3": f("CoOwnerName3"), "l3": f("CoOwnerLink3"), "b3": f("CoOwnerBusiness3"),
    })

    db.commit()
    return {"message": "Pricing updated"}


# ─── GET description ──────────────────────────────────────────────────────────

@router.get("/{animal_id}/description")
def get_description(animal_id: int, db: Session = Depends(get_db),
                     current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT Description FROM Animals WHERE AnimalID = :aid"), {"aid": animal_id}).fetchone()
    return {"Description": row.Description if row else ""}


# ─── POST update description ──────────────────────────────────────────────────

@router.post("/{animal_id}/update-description")
async def update_description(animal_id: int, request: Request,
                              db: Session = Depends(get_db),
                              current_user=Depends(get_current_user)):
    body = await request.json()
    db.execute(text("UPDATE Animals SET Description = :desc WHERE AnimalID = :aid"),
               {"desc": body.get("Description"), "aid": animal_id})
    db.commit()
    return {"message": "Description updated"}


# ─── GET ancestry ─────────────────────────────────────────────────────────────

@router.get("/{animal_id}/ancestry")
def get_ancestry(animal_id: int, db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT * FROM Ancestors WHERE AnimalID = :aid"), {"aid": animal_id}).fetchone()
    if not row:
        db.execute(text("INSERT INTO Ancestors (AnimalID) VALUES (:aid)"), {"aid": animal_id})
        db.commit()
        row = db.execute(text("SELECT * FROM Ancestors WHERE AnimalID = :aid"), {"aid": animal_id}).fetchone()
    animal = db.execute(text("SELECT SpeciesID FROM Animals WHERE AnimalID = :aid"), {"aid": animal_id}).fetchone()
    result = _row(row)
    result["SpeciesID"] = animal.SpeciesID if animal else None
    return result


# ─── POST update ancestry ─────────────────────────────────────────────────────

@router.post("/{animal_id}/update-ancestry")
async def update_ancestry(animal_id: int, request: Request,
                           db: Session = Depends(get_db),
                           current_user=Depends(get_current_user)):
    body = await request.json()
    f = lambda k: body.get(k) or None

    existing = db.execute(text("SELECT COUNT(*) FROM Ancestors WHERE AnimalID = :aid"), {"aid": animal_id}).scalar()
    fields = [
        "Sire","SireColor","SireLink",
        "SireSire","SireSireColor","SireSireLink",
        "SireSireSire","SireSireSireColor","SireSireSireLink",
        "SireSireDam","SireSireDamColor","SireSireDamLink",
        "SireDam","SireDamColor","SireDamLink",
        "SireDamSire","SireDamSireColor","SireDamSireLink",
        "SireDamDam","SireDamDamColor","SireDamDamLink",
        "Dam","DamColor","DamLink",
        "DamSire","DamSireColor","DamSireLink",
        "DamSireSire","DamSireSireColor","DamSireSireLink",
        "DamSireDam","DamSireDamColor","DamSireDamLink",
        "DamDam","DamDamColor","DamDamLink",
        "DamDamSire","DamDamSireColor","DamDamSireLink",
        "DamDamDam","DamDamDamColor","DamDamDamLink",
    ]
    params = {"aid": animal_id}
    params.update({fld: f(fld) for fld in fields})
    set_clause = ", ".join([f"{fld} = :{fld}" for fld in fields])

    if existing:
        db.execute(text(f"UPDATE Ancestors SET {set_clause} WHERE AnimalID = :aid"), params)
    else:
        cols = ", ".join(["AnimalID"] + fields)
        vals = ", ".join([":aid"] + [f":{fld}" for fld in fields])
        db.execute(text(f"INSERT INTO Ancestors ({cols}) VALUES ({vals})"), params)

    db.commit()
    return {"message": "Ancestry updated"}


# ─── GET fiber ────────────────────────────────────────────────────────────────

@router.get("/{animal_id}/fiber")
def get_fiber(animal_id: int, db: Session = Depends(get_db),
               current_user=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT FiberID, SampleDateYear, SampleDateMonth, SampleDateDay,
               Average, CF, StandardDev, CrimpPerInch, COV, Length,
               GreaterThan30, ShearWeight, Curve, BlanketWeight
        FROM Fiber WHERE AnimalID = :aid
        ORDER BY SampleDateYear DESC, Average DESC
    """), {"aid": animal_id}).fetchall()
    return [_row(r) for r in rows]


# ─── POST update fiber ────────────────────────────────────────────────────────

@router.post("/{animal_id}/update-fiber")
async def update_fiber(animal_id: int, request: Request,
                        db: Session = Depends(get_db),
                        current_user=Depends(get_current_user)):
    rows = await request.json()
    n = _nullable_float

    for row in rows:
        fiber_id = row.get("FiberID")
        params = {
            "aid": animal_id,
            "year": _nullable_int(row.get("SampleDateYear")),
            "avg": n(row.get("Average")), "cf": n(row.get("CF")),
            "sd": n(row.get("StandardDev")), "cpi": n(row.get("CrimpPerInch")),
            "cov": n(row.get("COV")), "length": n(row.get("Length")),
            "gt30": n(row.get("GreaterThan30")), "sw": n(row.get("ShearWeight")),
            "curve": n(row.get("Curve")), "bw": n(row.get("BlanketWeight")),
        }
        if fiber_id:
            params["fid"] = fiber_id
            db.execute(text("""
                UPDATE Fiber SET
                    SampleDateYear=:year, Average=:avg, CF=:cf,
                    StandardDev=:sd, CrimpPerInch=:cpi, COV=:cov, Length=:length,
                    GreaterThan30=:gt30, ShearWeight=:sw, Curve=:curve, BlanketWeight=:bw
                WHERE FiberID=:fid AND AnimalID=:aid
            """), params)
        else:
            if params["year"] or params["avg"]:
                db.execute(text("""
                    INSERT INTO Fiber (AnimalID, SampleDateYear, Average, CF,
                        StandardDev, CrimpPerInch, COV, Length,
                        GreaterThan30, ShearWeight, Curve, BlanketWeight)
                    VALUES (:aid, :year, :avg, :cf, :sd, :cpi, :cov, :length,
                        :gt30, :sw, :curve, :bw)
                """), params)

    db.commit()
    return {"message": "Fiber updated"}


# ─── GET awards ───────────────────────────────────────────────────────────────

@router.get("/{animal_id}/awards")
def get_awards(animal_id: int, db: Session = Depends(get_db),
                current_user=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT AwardsID, AwardYear, ShowName, Type, Placing, Awardcomments
        FROM awards
        WHERE AnimalID = :aid
          AND (LEN(ISNULL(Placing,'')) > 0 OR LEN(ISNULL(Class,'')) > 0
               OR LEN(ISNULL(AwardYear,'')) > 1 OR LEN(ISNULL(Awardcomments,'')) > 0
               OR LEN(ISNULL(ShowName,'')) > 0)
        ORDER BY AwardYear DESC, Placing DESC
    """), {"aid": animal_id}).fetchall()
    return [_row(r) for r in rows]


# ─── POST update awards ───────────────────────────────────────────────────────

@router.post("/{animal_id}/update-awards")
async def update_awards(animal_id: int, request: Request,
                         db: Session = Depends(get_db),
                         current_user=Depends(get_current_user)):
    rows = await request.json()

    for row in rows:
        awards_id = row.get("AwardsID")
        params = {
            "aid": animal_id,
            "year": row.get("AwardYear") or None,
            "show": row.get("ShowName") or None,
            "aclass": row.get("Type") or None,
            "placing": row.get("Placing") or None,
            "comments": row.get("Awardcomments") or None,
        }
        if awards_id:
            params["awid"] = awards_id
            db.execute(text("""
                UPDATE awards SET
                    AwardYear=:year, ShowName=:show, Type=:aclass,
                    Placing=:placing, Awardcomments=:comments
                WHERE AwardsID=:awid AND AnimalID=:aid
            """), params)
        else:
            db.execute(text("""
                INSERT INTO awards (AnimalID, AwardYear, ShowName, Type, Placing, Awardcomments)
                VALUES (:aid, :year, :show, :aclass, :placing, :comments)
            """), params)

    db.commit()
    return {"message": "Awards updated"}


# ─── POST publish toggle ──────────────────────────────────────────────────────

@router.post("/{animal_id}/publish")
async def toggle_publish(animal_id: int, request: Request,
                          db: Session = Depends(get_db),
                          current_user=Depends(get_current_user)):
    body = await request.json()
    val = 1 if body.get("publish") else 0
    db.execute(text("UPDATE Animals SET PublishForSale = :v WHERE AnimalID = :aid"),
               {"v": val, "aid": animal_id})
    db.commit()
    return {"published": bool(val)}
