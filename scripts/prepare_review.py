import sys
import asyncio
from beanie import init_beanie, PydanticObjectId

from src.database import init_db
from src.mapping.models import MappedDocument
from src.confidence.models import ConfidenceReport, FieldConfidence, ConfidenceClass, OverallClassification
from src.intake.models import UploadedImage
from src.common.enums import DocType

async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/prepare_review.py <processing_id>")
        sys.exit(1)
        
    processing_id = sys.argv[1]
    await init_db()
    
    # 1. Find the UploadedImage
    img = await UploadedImage.find_one(UploadedImage.processing_id == processing_id)
    if not img:
        print(f"Error: UploadedImage with processing_id '{processing_id}' not found in DB.")
        sys.exit(1)
        
    user_id = img.user_id
    
    # 2. Check if MappedDocument already exists
    mapped = await MappedDocument.find_one(MappedDocument.processing_id == processing_id)
    if not mapped:
        # Create a mock mapped document
        mapped = MappedDocument(
            processing_id=processing_id,
            doc_type=DocType.BUSINESS_CARD,
            user_id=user_id,
            extracted_fields={
                "name": "Nguyễn Văn A",
                "phone": "+84 912 345 678",
                "email": "nguyen.vana@company.com",
                "web": "www.company.com",
                "position": "Kỹ sư phần mềm",
                "company": "TECH SOLUTIONS JSC"
            },
            normalized_fields={
                "name": "Nguyễn Văn A",
                "phone": "+84912345678",
                "email": "nguyen.vana@company.com",
                "web": "https://www.company.com",
                "position": "Kỹ sư phần mềm",
                "company": "TECH SOLUTIONS JSC"
            },
            validation_results=[],
            missing_required_fields=[],
            mapping_status="mapped",
            mapper_version="1.0.0"
        )
        await mapped.insert()
        print(f"Created MappedDocument for {processing_id}")
    else:
        print(f"MappedDocument already exists for {processing_id}")
        
    # 3. Check if ConfidenceReport already exists
    report = await ConfidenceReport.find_one(ConfidenceReport.processing_id == processing_id)
    if not report:
        report = ConfidenceReport(
            processing_id=processing_id,
            mapped_document_id=mapped.id,
            document_type=DocType.BUSINESS_CARD,
            raw_ocr_output={"raw_text": "Nguyễn Văn A\n+84 912 345 678\nnguyen.vana@company.com\nwww.company.com\nKỹ sư phần mềm\nTECH SOLUTIONS JSC"},
            normalized_fields=mapped.normalized_fields,
            validation_results=[],
            field_scores=[
                FieldConfidence(field_name="name", value="Nguyễn Văn A", score=0.98, classification=ConfidenceClass.HIGH, auto_approved=True),
                FieldConfidence(field_name="phone", value="+84912345678", score=0.99, classification=ConfidenceClass.HIGH, auto_approved=True),
                FieldConfidence(field_name="email", value="nguyen.vana@company.com", score=0.97, classification=ConfidenceClass.HIGH, auto_approved=True),
                FieldConfidence(field_name="web", value="https://www.company.com", score=0.95, classification=ConfidenceClass.HIGH, auto_approved=True),
                FieldConfidence(field_name="position", value="Kỹ sư phần mềm", score=0.92, classification=ConfidenceClass.LOW, auto_approved=False),
                FieldConfidence(field_name="company", value="TECH SOLUTIONS JSC", score=0.99, classification=ConfidenceClass.HIGH, auto_approved=True)
            ],
            overall_score=0.97,
            classification=OverallClassification.SUCCESS,
            flags={"requires_manual_review": False},
            failed_fields=[],
            metadata={"business_card_schema": "business_card"}
        )
        await report.insert()
        print(f"Created ConfidenceReport for {processing_id}")
    else:
        print(f"ConfidenceReport already exists for {processing_id}")
        
    # 4. Update image status to ready_for_review so client knows it is processed
    img.status = "ready_for_review"
    await img.save()
    print(f"Updated status of UploadedImage {processing_id} to 'ready_for_review'")
    print("Success! You can now test the review/confirm/final endpoints in Swagger.")

if __name__ == "__main__":
    asyncio.run(main())
