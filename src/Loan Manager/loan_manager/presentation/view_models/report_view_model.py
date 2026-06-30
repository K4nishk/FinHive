from loan_manager.application.dtos.report_dto import ReportDTO, ReportRecordDTO


class ReportViewModel:
    @staticmethod
    def to_display_row(dto: ReportDTO) -> dict:
        return {
            "report_id": dto.report_id,
            "mode": dto.report_mode.value,
            "status": dto.status.value,
            "records_count": str(len(dto.records)),
            "created_at": dto.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": dto.updated_at.strftime("%Y-%m-%d %H:%M"),
        }
