from integrations.slack.attachments import classify_attachment


class TestClassifyAttachment:
    def test_images_are_binary(self) -> None:
        for mt in ("image/png", "image/jpeg", "image/gif", "image/webp"):
            assert classify_attachment(mt) == "binary"

    def test_pdf_is_binary(self) -> None:
        assert classify_attachment("application/pdf") == "binary"

    def test_text_prefix_is_text(self) -> None:
        assert classify_attachment("text/plain") == "text"
        assert classify_attachment("text/x-python") == "text"

    def test_known_application_text_types(self) -> None:
        assert classify_attachment("application/json") == "text"
        assert classify_attachment("image/svg+xml") == "text"

    def test_unknown_binary_is_unsupported(self) -> None:
        assert classify_attachment("application/zip") == "unsupported"
        assert classify_attachment("application/octet-stream") == "unsupported"
        assert classify_attachment("video/mp4") == "unsupported"
