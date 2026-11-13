document.addEventListener("DOMContentLoaded", function () {
    var modal = document.getElementById("previewModal");
    if (!modal) return;
    var frame = document.getElementById("previewFrame");
    var download = document.getElementById("previewDownloadLink");

    document.querySelectorAll("[data-bs-target='#previewModal'][data-preview-url]").forEach(
        function (button) {
            button.addEventListener("click", function () {
                var url = button.dataset.previewUrl;
                frame.src = url;
                if (download) {
                    download.href = url.replace(/\/preview\/$/, "/download/");
                    download.textContent = "Descarregar original";
                    download.classList.remove("d-none");
                }
            });
        }
    );

    modal.addEventListener("hidden.bs.modal", function () {
        frame.src = "";
        if (download) {
            download.classList.add("d-none");
        }
    });
});
