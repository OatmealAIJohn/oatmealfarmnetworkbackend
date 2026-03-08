from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import datetime

router = APIRouter(prefix="/api/businesses", tags=["businesses"])


def clean(val):
    """Return None if value is null, '0', or empty string."""
    if val is None:
        return None
    if str(val).strip() in ("0", ""):
        return None
    return val


def build_logo_url(logo):
    """Build full logo URL handling /uploads/ prefix or bare filename."""
    if not logo or str(logo).strip() in ("0", ""):
        return None
    if logo.startswith("/"):
        return "https://www.oatmealfarmnetwork.com" + logo
    return "https://www.oatmealfarmnetwork.com/uploads/" + logo


@router.get("/countries")
def get_countries(db: Session = Depends(get_db)):
    try:
        countries = db.query(models.Country.name).order_by(models.Country.name).all()
        return [c[0] for c in countries if c[0]]
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/states")
def get_states(country: str, db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text
        rows = db.execute(
            text("""SELECT sp.StateIndex, sp.name
                    FROM state_province sp
                    JOIN country c ON sp.country_id = c.country_id
                    WHERE c.name = :country
                    ORDER BY sp.name"""),
            {"country": country}
        ).fetchall()
        return [{"StateIndex": r.StateIndex, "name": r.name} for r in rows]
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types")
def get_business_types(db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text
        rows = db.execute(
            text("SELECT BusinessTypeID, BusinessType FROM businesstypelookup ORDER BY BusinessType")
        ).fetchall()
        return [{"BusinessTypeID": r.BusinessTypeID, "BusinessType": r.BusinessType} for r in rows]
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
def create_account(payload: dict, db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text

        people_id = payload.get("PeopleID")
        if not people_id:
            raise HTTPException(status_code=400, detail="PeopleID is required")

        # 1. Create Address record
        address = models.Address(
            AddressStreet = payload.get("AddressStreet", ""),
            AddressCity   = payload.get("AddressCity", ""),
            AddressState  = payload.get("StateIndex", ""),
            AddressZip    = payload.get("AddressZip", ""),
        )
        db.add(address)
        db.flush()

        # 2. Create Websites record if website provided
        websites_id = None
        website = payload.get("BusinessWebsite", "")
        if website:
            ws = models.Websites(Website=website)
            db.add(ws)
            db.flush()
            websites_id = ws.WebsitesID

        # 3. Create Business record
        business = models.Business(
            BusinessTypeID    = payload.get("BusinessTypeID"),
            BusinessName      = payload.get("BusinessName", ""),
            AddressID         = address.AddressID,
            WebsitesID        = websites_id,
            SubscriptionLevel = 0,
            AccessLevel       = 1,
        )
        db.add(business)
        db.flush()

        # 4. Create BusinessAccess record linking user to business
        access = models.BusinessAccess(
            BusinessID    = business.BusinessID,
            PeopleID      = int(people_id),
            AccessLevelID = 1,
            Active        = 1,
            CreatedAt     = datetime.datetime.utcnow(),
            Role          = "Owner",
        )
        db.add(access)

        # 5. Update People phone if provided
        phone = payload.get("PeoplePhone", "")
        if phone:
            db.execute(
                text("UPDATE People SET PeoplePhone = :phone WHERE PeopleID = :pid"),
                {"phone": phone, "pid": int(people_id)}
            )

        db.commit()
        return {"BusinessID": business.BusinessID, "message": "Account created successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug")
def debug_businesses(db: Session = Depends(get_db)):
    countries = db.query(models.Country.name).limit(20).all()
    sample = (
        db.query(models.Business.BusinessName, models.Country.name)
        .join(models.Address, models.Business.AddressID == models.Address.AddressID)
        .join(models.Country, models.Address.country_id == models.Country.country_id)
        .limit(10)
        .all()
    )
    return {
        "countries": [c[0] for c in countries],
        "sample_businesses": [{"name": b[0], "country": b[1]} for b in sample]
    }


@router.get("/")
def get_businesses(
    country: str = None,
    BusinessTypeID: int = None,
    state: str = None,
    db: Session = Depends(get_db)
):
    try:
        query = (
            db.query(
                models.Business,
                models.Address,
                models.BusinessTypeLookup,
                models.Country,
                models.Websites
            )
            .outerjoin(models.Address, models.Business.AddressID == models.Address.AddressID)
            .outerjoin(models.BusinessTypeLookup, models.Business.BusinessTypeID == models.BusinessTypeLookup.BusinessTypeID)
            .outerjoin(models.Country, models.Address.country_id == models.Country.country_id)
            .outerjoin(models.Websites, models.Business.WebsitesID == models.Websites.WebsitesID)
        )

        if BusinessTypeID:
            query = query.filter(models.Business.BusinessTypeID == BusinessTypeID)
        if country:
            query = query.filter(models.Country.name == country)
        if state:
            query = query.filter(models.Address.AddressState == state)

        query = query.order_by(models.Business.BusinessName)
        results = query.all()

        businesses = []
        for B, A, BT, C, W in results:
            businesses.append({
                "BusinessID":           B.BusinessID,
                "BusinessName":         B.BusinessName,
                "BusinessEmail":        B.BusinessEmail,
                "BusinessPhone":        B.BusinessPhone,
                "BusinessTypeID":       B.BusinessTypeID,
                "BusinessType":         BT.BusinessType if BT else None,
                "AddressStreet":        clean(A.AddressStreet if A else None),
                "AddressCity":          clean(A.AddressCity if A else None),
                "AddressState":         clean(A.AddressState if A else None),
                "AddressZip":           clean(A.AddressZip if A else None),
                "AddressCountry":       C.name if C else None,
                "ProfileImage":         build_logo_url(B.Logo),
                "BusinessWebsite":      W.Website if W and W.Website else None,
                "BusinessFacebook":     B.BusinessFacebook,
                "BusinessInstagram":    B.BusinessInstagram,
                "BusinessLinkedIn":     B.BusinessLinkedIn,
                "BusinessX":            B.BusinessX,
                "BusinessPinterest":    B.BusinessPinterest,
                "BusinessYouTube":      B.BusinessYouTube,
                "BusinessTruthSocial":  B.BusinessTruthSocial,
                "BusinessBlog":         B.BusinessBlog,
                "BusinessOtherSocial1": B.BusinessOtherSocial1,
                "BusinessOtherSocial2": B.BusinessOtherSocial2,
            })

        return businesses

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── PROFILE endpoints ─────────────────────────────────────────────

@router.get("/profile/{business_id}")
def get_profile(business_id: int, db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text

        row = db.execute(text("""
            SELECT
                b.BusinessID, b.BusinessName, b.BusinessEmail,
                b.BusinessPhone, b.AddressID, b.WebsitesID,
                b.Contact1PeopleID,
                a.AddressStreet, a.AddressApt, a.AddressCity,
                a.AddressState, a.AddressZip, a.StateIndex, a.country_id,
                w.Website,
                p.PeopleFirstName, p.PeopleLastName, p.PeopleEmail,
                p.PeoplePhone AS ContactPhone,
                c.name AS country_name
            FROM Business b
            LEFT JOIN Address a ON b.AddressID = a.AddressID
            LEFT JOIN Websites w ON b.WebsitesID = w.WebsitesID
            LEFT JOIN People p ON b.Contact1PeopleID = p.PeopleID
            LEFT JOIN country c ON a.country_id = c.country_id
            WHERE b.BusinessID = :bid
        """), {"bid": business_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Business not found")

        # Fetch phone/cell/fax from Phone table if exists
        phone_row = None
        if row.BusinessID:
            phone_row = db.execute(text("""
                SELECT Phone, CellPhone, Fax FROM Phone
                WHERE PhoneID = (SELECT PhoneID FROM Business WHERE BusinessID = :bid)
            """), {"bid": business_id}).fetchone()

        return {
            "BusinessID":       row.BusinessID,
            "BusinessName":     row.BusinessName,
            "BusinessEmail":    row.BusinessEmail,
            "BusinessWebsite":  row.Website,
            "AddressStreet":    row.AddressStreet,
            "AddressApt":       row.AddressApt,
            "AddressCity":      row.AddressCity,
            "AddressState":     row.AddressState,
            "AddressZip":       row.AddressZip,
            "StateIndex":       row.StateIndex,
            "country_id":       row.country_id,
            "country_name":     row.country_name or "USA",
            "ContactFirstName": row.PeopleFirstName,
            "ContactLastName":  row.PeopleLastName,
            "ContactEmail":     row.PeopleEmail or row.BusinessEmail,
            "BusinessPhone":    phone_row.Phone if phone_row else row.BusinessPhone,
            "BusinessCell":     phone_row.CellPhone if phone_row else None,
            "BusinessFax":      phone_row.Fax if phone_row else None,
            "WebsitesID":       row.WebsitesID,
            "AddressID":        row.AddressID,
            "Contact1PeopleID": row.Contact1PeopleID,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/profile/{business_id}")
def update_profile(business_id: int, payload: dict, db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text

        # Get current IDs
        ids = db.execute(text("""
            SELECT AddressID, WebsitesID, Contact1PeopleID,
                   PhoneID FROM Business WHERE BusinessID = :bid
        """), {"bid": business_id}).fetchone()

        if not ids:
            raise HTTPException(status_code=404, detail="Business not found")

        # 1. Update Address
        if ids.AddressID:
            db.execute(text("""
                UPDATE Address SET
                    AddressStreet = :street,
                    AddressApt    = :apt,
                    AddressCity   = :city,
                    StateIndex    = :state,
                    AddressZip    = :zip,
                    country_id    = (SELECT country_id FROM country WHERE name = :country)
                WHERE AddressID = :aid
            """), {
                "street":  payload.get("AddressStreet", ""),
                "apt":     payload.get("AddressApt", ""),
                "city":    payload.get("AddressCity", ""),
                "state":   payload.get("StateIndex") or None,
                "zip":     payload.get("AddressZip", ""),
                "country": payload.get("country_name", "USA"),
                "aid":     ids.AddressID,
            })

        # 2. Update Website
        website = payload.get("BusinessWebsite", "")
        if website.lower().startswith("http://"):
            website = website[7:]
        if ids.WebsitesID:
            db.execute(text("UPDATE Websites SET Website = :w WHERE WebsitesID = :wid"),
                       {"w": website, "wid": ids.WebsitesID})

        # 3. Update or insert Phone
        phone = payload.get("BusinessPhone", "")
        cell  = payload.get("BusinessCell", "")
        fax   = payload.get("BusinessFax", "")
        if ids.PhoneID:
            db.execute(text("""
                UPDATE Phone SET Phone = :phone, CellPhone = :cell, Fax = :fax
                WHERE PhoneID = :pid
            """), {"phone": phone, "cell": cell, "fax": fax, "pid": ids.PhoneID})
        else:
            db.execute(text("""
                INSERT INTO Phone (Phone, CellPhone, Fax) VALUES (:phone, :cell, :fax)
            """), {"phone": phone, "cell": cell, "fax": fax})

        # 4. Update Contact (People)
        if ids.Contact1PeopleID:
            db.execute(text("""
                UPDATE People SET
                    PeopleFirstName = :fn,
                    PeopleLastName  = :ln,
                    PeopleEmail     = :email
                WHERE PeopleID = :pid
            """), {
                "fn":    payload.get("ContactFirstName", ""),
                "ln":    payload.get("ContactLastName", ""),
                "email": payload.get("ContactEmail", ""),
                "pid":   ids.Contact1PeopleID,
            })

        # 5. Update Business name
        db.execute(text("""
            UPDATE Business SET BusinessName = :name, BusinessEmail = :email
            WHERE BusinessID = :bid
        """), {
            "name":  payload.get("BusinessName", ""),
            "email": payload.get("ContactEmail", ""),
            "bid":   business_id,
        })

        db.commit()
        return {"message": "Profile updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{business_id}")
def delete_business(business_id: int, db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text

        # Get related IDs before deleting
        ids = db.execute(text("""
            SELECT WebsitesID, PhoneID, AddressID
            FROM Business WHERE BusinessID = :bid
        """), {"bid": business_id}).fetchone()

        if not ids:
            raise HTTPException(status_code=404, detail="Business not found")

        # 1. Delete BusinessAccess records
        db.execute(text("DELETE FROM BusinessAccess WHERE BusinessID = :bid"),
                   {"bid": business_id})

        # 2. Delete Business record
        db.execute(text("DELETE FROM Business WHERE BusinessID = :bid"),
                   {"bid": business_id})

        # 3. Delete Phone if exists
        if ids.PhoneID:
            db.execute(text("DELETE FROM Phone WHERE PhoneID = :pid"),
                       {"pid": ids.PhoneID})

        # 4. Delete Website if exists
        if ids.WebsitesID:
            db.execute(text("DELETE FROM Websites WHERE WebsitesID = :wid"),
                       {"wid": ids.WebsitesID})

        # 5. Delete Address if exists
        if ids.AddressID:
            db.execute(text("DELETE FROM Address WHERE AddressID = :aid"),
                       {"aid": ids.AddressID})

        db.commit()
        return {"message": "Account deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))