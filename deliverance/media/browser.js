google.load("jquery", "1");
var deliveranceSelector = null;
var selectedElement = null;

google.setOnLoadCallback(function() {
  var selector = $('#deliverance-ids').get(0);
  deliveranceSelector = selector;
  var uniqueClasses = {};
  var dupClasses = {};
  $("*").get().map(function (el) {
    if (el.id == 'deliverance-ids' || el.id == 'deliverance-browser') {
      return;
    }
    if (el.id) {
      var option = document.createElement('option');
      option.value = '#' + el.id;
      option.innerHTML = '#' + el.id;
      selector.appendChild(option);
    }
    if (el.className) {
      var allClasses = el.className.split();
      allClasses.map(function (className) {
        if (! dupClasses[className]) {
          if (uniqueClasses[className]) {
            dupClasses[className] = true;
            uniqueClasses[className] = undefined;
          } else {
            uniqueClasses[className] = true;
          }
        }
      });
    }
  });
  for (var className in uniqueClasses) {
    if (! uniqueClasses[className]) {
      continue;
    }
    var option = document.createElement('option');
    option.value = '.'+className;
    option.innerHTML = '.'+className;
    selector.appendChild(option);
  }
});

function deliveranceChangeId() {
  var option = deliveranceSelector.value;
  if (selectedElement) {
    selectedElement.removeClass('deliverance-highlight');
  }
  selectedElement = $(option);
  selectedElement.addClass('deliverance-highlight');
}

