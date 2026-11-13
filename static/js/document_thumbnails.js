document.addEventListener("DOMContentLoaded", function () {
    var thumbs = Array.prototype.slice.call(
        document.querySelectorAll("[data-thumbnail-url]")
    );
    if (!thumbs.length) return;

    import("/static/vendor/pdfjs/pdf.min.mjs")
        .then(function (pdfjs) {
            pdfjs.GlobalWorkerOptions.workerSrc =
                "/static/vendor/pdfjs/pdf.worker.min.mjs";

            function showFallback(span, iconClass) {
                var canvas = span.querySelector("canvas");
                var fallback = span.querySelector(".document-thumbnail-fallback");
                if (canvas) canvas.classList.add("d-none");
                if (fallback) {
                    fallback.style.display = "";
                    var icon = fallback.querySelector("i");
                    if (icon && iconClass) icon.className = iconClass + " fs-1";
                }
            }

            function renderThumb(span) {
                var canvas = span.querySelector("canvas");
                if (!canvas || span.dataset.rendered) return;
                span.dataset.rendered = "1";

                fetch(span.dataset.thumbnailUrl, { credentials: "same-origin" })
                    .then(function (response) {
                        if (!response.ok) {
                            var icon =
                                response.status === 422
                                    ? "bi-file-earmark-word"
                                    : "bi-file-earmark";
                            showFallback(span, icon);
                            return null;
                        }
                        return response.arrayBuffer();
                    })
                    .then(function (data) {
                        if (!data) return null;
                        return pdfjs.getDocument({ data: data }).promise;
                    })
                    .then(function (pdf) {
                        if (!pdf) return null;
                        return pdf.getPage(1);
                    })
                    .then(function (page) {
                        if (!page) return null;
                        var base = page.getViewport({ scale: 1 });
                        var viewport = page.getViewport({
                            scale: 320 / base.width,
                        });
                        canvas.width = viewport.width;
                        canvas.height = viewport.height;
                        return page.render({
                            canvasContext: canvas.getContext("2d"),
                            viewport: viewport,
                        }).promise;
                    })
                    .then(function () {
                        canvas.classList.remove("d-none");
                    })
                    .catch(function () {
                        showFallback(span, "bi-file-earmark");
                    });
            }

            var observer = new IntersectionObserver(
                function (entries) {
                    entries.forEach(function (entry) {
                        if (entry.isIntersecting) {
                            observer.unobserve(entry.target);
                            renderThumb(entry.target);
                        }
                    });
                },
                { rootMargin: "160px" }
            );

            thumbs.forEach(function (span) {
                observer.observe(span);
            });
        })
        .catch(function () {
            thumbs.forEach(function (span) {
                showFallback(span, "bi-file-earmark");
            });
        });
});
