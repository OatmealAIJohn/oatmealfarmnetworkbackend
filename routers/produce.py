from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import get_db

router = APIRouter(prefix="/api/produce", tags=["produce"])


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    try:
        rows = db.execute(text(
            "SELECT IngredientCategoryID, IngredientCategory FROM IngredientCategoryLookup ORDER BY IngredientCategory"
        )).fetchall()
        return [{"IngredientCategoryID": r.IngredientCategoryID, "IngredientCategory": r.IngredientCategory} for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingredients")
def get_ingredients(IngredientCategoryID: int, db: Session = Depends(get_db)):
    try:
        rows = db.execute(text(
            "SELECT IngredientID, IngredientName FROM Ingredients WHERE IngredientCategoryID = :cid ORDER BY IngredientName"
        ), {"cid": IngredientCategoryID}).fetchall()
        return [{"IngredientID": r.IngredientID, "IngredientName": r.IngredientName} for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/measurements")
def get_measurements(db: Session = Depends(get_db)):
    try:
        rows = db.execute(text(
            "SELECT MeasurementID, Measurement, MeasurementAbbreviation FROM MeasurementLookup ORDER BY MeasurementOrder"
        )).fetchall()
        return [{"MeasurementID": r.MeasurementID, "Measurement": r.Measurement, "MeasurementAbbreviation": r.MeasurementAbbreviation} for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inventory")
def get_inventory(BusinessID: int, db: Session = Depends(get_db)):
    try:
        rows = db.execute(text("""
            SELECT p.ProduceID, p.IngredientID, p.Quantity, p.MeasurementID,
                   p.WholesalePrice, p.RetailPrice, p.AvailableDate, p.ShowProduce,
                   i.IngredientName,
                   m.Measurement, m.MeasurementAbbreviation
            FROM Produce p
            JOIN Ingredients i ON p.IngredientID = i.IngredientID
            JOIN MeasurementLookup m ON p.MeasurementID = m.MeasurementID
            WHERE p.BusinessID = :bid
            ORDER BY i.IngredientName
        """), {"bid": BusinessID}).fetchall()
        return [
            {
                "ProduceID":              r.ProduceID,
                "IngredientID":           r.IngredientID,
                "IngredientName":         r.IngredientName,
                "Quantity":               r.Quantity,
                "MeasurementID":          r.MeasurementID,
                "Measurement":            r.Measurement,
                "MeasurementAbbreviation":r.MeasurementAbbreviation,
                "WholesalePrice":         float(r.WholesalePrice) if r.WholesalePrice is not None else None,
                "RetailPrice":            float(r.RetailPrice) if r.RetailPrice is not None else None,
                "AvailableDate":          str(r.AvailableDate) if r.AvailableDate else None,
                "ShowProduce":            r.ShowProduce,
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
def add_produce(payload: dict, db: Session = Depends(get_db)):
    try:
        db.execute(text("""
            INSERT INTO Produce (IngredientID, Quantity, MeasurementID, WholesalePrice, RetailPrice, BusinessID, AvailableDate)
            VALUES (:ingredient, :qty, :meas, :wholesale, :retail, :bid, :avail)
        """), {
            "ingredient": payload.get("IngredientID") or None,
            "qty":        payload.get("Quantity") or None,
            "meas":       payload.get("MeasurementID") or None,
            "wholesale":  payload.get("WholesalePrice") or None,
            "retail":     payload.get("RetailPrice") or None,
            "bid":        payload.get("BusinessID"),
            "avail":      payload.get("AvailableDate") or None,
        })
        db.commit()
        return {"message": "Produce added successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{produce_id}")
def update_produce(produce_id: int, payload: dict, BusinessID: int, db: Session = Depends(get_db)):
    try:
        db.execute(text("""
            UPDATE Produce SET
                Quantity      = :qty,
                MeasurementID = :meas,
                RetailPrice   = :retail,
                WholesalePrice= :wholesale,
                AvailableDate = :avail,
                ShowProduce   = :show,
                IngredientID  = :ingredient
            WHERE ProduceID = :pid AND BusinessID = :bid
        """), {
            "qty":        payload.get("Quantity") or None,
            "meas":       payload.get("MeasurementID") or None,
            "retail":     payload.get("RetailPrice") or None,
            "wholesale":  payload.get("WholesalePrice") or None,
            "avail":      payload.get("AvailableDate") or None,
            "show":       payload.get("ShowProduce", 0),
            "ingredient": payload.get("IngredientID") or None,
            "pid":        produce_id,
            "bid":        BusinessID,
        })
        db.commit()
        return {"message": "Produce updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{produce_id}")
def delete_produce(produce_id: int, BusinessID: int, db: Session = Depends(get_db)):
    try:
        db.execute(text(
            "DELETE FROM Produce WHERE ProduceID = :pid AND BusinessID = :bid"
        ), {"pid": produce_id, "bid": BusinessID})
        db.commit()
        return {"message": "Produce deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
