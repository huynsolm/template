// M8-A automatic alignment, applied before capture and whenever page.html is reopened.
// A section with data-align="auto" is centred when it has no list and every
// supporting paragraph fits in two lines; otherwise it is aligned left.
(function () {
  function lineCount(element) {
    var range = document.createRange();
    range.selectNodeContents(element);
    var tops = [];
    var rects = range.getClientRects();
    for (var i = 0; i < rects.length; i++) {
      var r = rects[i];
      if (r.width <= 0 || r.height <= 0) continue;
      if (!tops.some(function (t) { return Math.abs(t - r.top) < r.height / 2; })) tops.push(r.top);
    }
    return tops.length;
  }
  function apply() {
    var sections = document.querySelectorAll('main > section[data-align]');
    for (var i = 0; i < sections.length; i++) {
      var section = sections[i];
      var mode = section.getAttribute('data-align');
      if (mode === 'auto') {
        var hasList = section.querySelector('li, .point, dl > div') !== null || section.querySelectorAll('h3').length > 1;
        var long = false;
        var paragraphs = section.querySelectorAll('p:not(.price)');
        for (var j = 0; j < paragraphs.length; j++) {
          if (lineCount(paragraphs[j]) > 2) { long = true; break; }
        }
        mode = (hasList || long) ? 'left' : 'center';
      }
      section.classList.remove('copy-align-center', 'copy-align-left');
      section.classList.add('copy-align-' + mode);
    }
    document.documentElement.setAttribute('data-layout-done', '1');
  }
  document.fonts.ready.then(apply);
})();
