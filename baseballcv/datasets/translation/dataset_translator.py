from .formats import YOLOFmt, COCOFmt, PascalFmt, JsonLFmt

TRANSLATOR = {
    'yolo': YOLOFmt,
    'pascal': PascalFmt,
    'coco': COCOFmt,
    'jsonl': JsonLFmt

}

class DatasetTranslator:
    """
    Class that translates various dataset formats across the Computer Vision
    space.

    Args:
        format_name (str): The current format of your dataset
        conversion_name (str): The format of the desired translation
        root_dir (str): The directory pointing to your dataset
        conversion_dir (str): The name of the directory for conversions. Defaults to 'dataset_conversion'
        force_masks (bool): If segmentation is involved. Defaults to False
        is_obb (bool): If labels are in OBB format, used for YOLO
    """
    def __init__(
            self, 
            format_name: str, 
            conversion_name: str,
            root_dir: str,
            conversion_dir: str = 'dataset_conversion',
            *,
            force_masks: bool = False,
            is_obb: bool = False
            ) -> None:
        
        format_name = format_name.lower().strip()
        conversion_name = conversion_name.lower().strip()

        if (format_name == 'jsonl' or conversion_name == 'jsonl') and force_masks:
            raise ValueError('We are not supporting msking for JSONL yet. Please reach out to the maintainers if you want segmentation incorporated. ')

        if format_name not in TRANSLATOR:
            raise ValueError(f"Invalid format: {format_name}",
                             f"These are the supported formats: {', '.join(list(TRANSLATOR.keys()))}")
        
        self.fmt_instance = TRANSLATOR[format_name](root_dir, conversion_dir, force_masks, is_obb)

        if not hasattr(self.fmt_instance, f'to_{conversion_name}'):
            raise ValueError(f'Unsupported format: {format_name} -> {conversion_name}')
        
        self._convert_fn = getattr(self.fmt_instance, f'to_{conversion_name}')

    def convert(self) -> None:
        """
        Converts to desired dataset format based on constructor args.
        """
        self._convert_fn()