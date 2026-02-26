// Matomo Analytics for Dev Agents Documentation
var _paq = window._paq = window._paq || [];
_paq.push(['enableLinkTracking']);
_paq.push(['enableHeartBeatTimer']);

(function() {
  var u = "//m.codeligence.ai/";
  _paq.push(['setTrackerUrl', u + 'matomo.php']);
  _paq.push(['setSiteId', '7']);
  var d = document, g = d.createElement('script'), s = d.getElementsByTagName('script')[0];
  g.async = true; g.src = u + 'matomo.js'; s.parentNode.insertBefore(g, s);
})();

// Track button clicks with button id and text
document.addEventListener('click', function(e) {
  var button = e.target.closest('button, a.md-button, [role="button"]');
  if (button) {
    var id = button.id || 'no-id';
    var text = (button.textContent || '').trim().substring(0, 100);
    _paq.push(['trackEvent', 'Click', 'Button', id + ': ' + text]);
  }
});

// Track scroll depth (fires once per threshold per page)
var scrollThresholds = { 25: false, 50: false, 75: false, 100: false };

function trackScroll() {
  var scrollDepth = Math.round(
    ((window.scrollY + window.innerHeight) / document.documentElement.scrollHeight) * 100
  );
  for (var threshold in scrollThresholds) {
    if (!scrollThresholds[threshold] && scrollDepth >= threshold) {
      scrollThresholds[threshold] = true;
      _paq.push(['trackEvent', 'Engagement', 'Scroll Depth', threshold + '%']);
    }
  }
}

window.addEventListener('scroll', trackScroll);

// Handle initial load and instant navigation (virtual page views)
document$.subscribe(function() {
  // Reset scroll tracking for the new page
  scrollThresholds = { 25: false, 50: false, 75: false, 100: false };
  _paq.push(['setCustomUrl', location.pathname]);
  _paq.push(['setDocumentTitle', document.title]);
  _paq.push(['trackPageView']);
});
