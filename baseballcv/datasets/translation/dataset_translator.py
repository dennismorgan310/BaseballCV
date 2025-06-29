from .formats import YOLOFmt, COCOFmt, PascalFmt, JsonLFmt

TRANSLATOR = {
    'yolo': YOLOFmt,
    'pascal': PascalFmt,
    'coco': COCOFmt,
    'jsonl': JsonLFmt

}

class DatasetTranslator:
    def __init__(
            self, 
            format_name: str, 
            conversion_name: str,
            root_dir: str,
            *,
            force_masks: bool = False,
            is_obb: bool = False
            ) -> None:
        
        format_name = format_name.lower().strip()
        conversion_name = conversion_name.lower().strip()

        if format_name not in TRANSLATOR:
            raise ValueError(f"Invalid format: {format_name}",
                             f"These are the supported formats: {', '.join(list(TRANSLATOR.keys()))}")
        
        self.fmt_instance = TRANSLATOR[format_name](root_dir, force_masks, is_obb)

        if not hasattr(self.fmt_instance, f'to_{conversion_name}'):
            raise ValueError(f'Unsupported format: {format_name} -> {conversion_name}')
        
        self._convert_fn = getattr(self.fmt_instance, f'to_{conversion_name}')

    def convert(self) -> None:
        self._convert_fn()