/**
 * Shortcode Popup Previews
 *
 * On mouseenter over any <a class="shortcode-link"> element, fetches a
 * lightweight summary from /api/entity-preview/<type>/<id> and shows a
 * Bootstrap popover with the entity name, subtitle, and status.
 *
 * Does nothing on pages with no shortcode links.
 */
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('a.shortcode-link').forEach(function (link) {
        link.addEventListener('mouseenter', function () {
            if (this._popoverLoaded) return;
            var self = this;
            fetch('/api/entity-preview/' + this.dataset.previewType + '/' + this.dataset.previewId)
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    var parts = [];
                    if (data.subtitle) parts.push(data.subtitle);
                    if (data.status)   parts.push(data.status);
                    var pop = new bootstrap.Popover(self, {
                        title:     data.name || '—',
                        content:   parts.join(' · ') || '—',
                        trigger:   'hover focus',
                        placement: 'top',
                        html:      false
                    });
                    pop.show();
                    self._popoverLoaded = true;
                })
                .catch(function () {}); // silently ignore failures
        });
    });
});
