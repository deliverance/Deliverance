if (typeof console == 'undefined') {
    console = {log: function () {}};
}

if (typeof Deliverance == 'undefined') {
    Deliverance = {};
}

Deliverance.deliveranceURL = '__DELIVERANCE_URL__';

Deliverance.startAction = function (location) {
    var req = XMLHttpRequest();
    req.onreadystatechange = function () {
        if (req.readyState == 4) {
            if (req.status != 200) {
                var div = document.createElement('div')
                div.innerHTML = req.responseText;
                var body = document.getElementsByTagName('body')[0];
                body.insertBefore(div, body.childNodes[0]);
                return;
            }
            var data = eval(req.responseText);
            for (var i=0; i<data.length; i++) {
                Deliverance.processAction(data[i]);
            }
        }
    };
    req.open('GET', location, true);
    req.send(null);
};

Deliverance.startAction(Deliverance.deliveranceURL + '/.deliverance/subreq?url=' + encodeURIComponent(location));

Deliverance.processAction = function (action) {
    console.log('action:', action['type'], action['mode'], action['selector']);
    if (action['type'] == 'replace') {
        var el = Deliverance.selectElement(action['selector']);
        if (action['mode'] == 'children') {
            el.innerHTML = action['content'];
        } else if (action['mode'] == 'element') {
            var newEl = document.createElement('div');
            newEl.innerHTML = action['content'];
            for (var i=0; i<newEl.childNodes.length; i++) {
                el.parentNode.insertBefore(newEl.childNodes[i], el);
            }
            el.parentNode.removeChild(el);
        } else if (action['mode'] == 'attributes' || action['mode'] == 'tag') {
            while (el.hasAttributes()) {
                el.removeAttributeNode(el.attributes[0]);
            }
            for (var i in action['attributes']) {
                el.setAttribute(i, action['attributes'][i]);
            }
            if (action['mode'] == 'tag') {
                el.tagName = action['tagName'];
            }
        }
    } else if (action['type'] == 'append' || action['type'] == 'prepend') {
        var append = action['type'] == 'append';
        var el = Deliverance.selectElement(action['selector']);
        if (action['mode'] == 'children') {
            if (append) {
                el.innerHTML += action['content'];
            } else {
                el.innerHTML = action['content'] + el.innerHTML;
            }
        } else if (action['mode'] == 'element') {
            var newEl = document.createElement('div');
            newEl.innerHTML = action['content'];
            if (append) {
                var next = el.nextSibling;
                while (newEl.childNodes.length) {
                    var last = newEl.childNodes[newEl.childNodes.length-1];
                    if (next !== null) {
                        el.parentNode.insertBefore(last, next);
                    } else {
                        el.parentNode.appendChild(last);
                    }
                }
            } else {
                for (var i=0; i<newEl.childNodes.length; i++) {
                    el.parentNode.insertBefore(newEl.childNodes[i], el);
                }
            }
        } else if (action['mode'] == 'attributes') {
            for (var i in action['attributes']) {
                if (! append || ! el.hasAttribute(i)) {
                    el.setAttribute(i, action['attributes'][i]);
                }
            }
        }
    } else if (action['mode'] == 'include') {
        Deliverance.startAction(action['callback']);
    } else {
        throw('Unknown action mode: '+action['mode']);
    }
}

Deliverance.selectElement = function (selector) {
    if (selector.charAt(0) == '#') {
        var el = document.getElementById(selector.substr(1));
        if (el === null) {
            throw('Selector returned no elements: '+selector);
        }
        return el;
    } else if (selector.charAt(0) == '/') {
        var parts = selector.substr(1).split('/');
        var el = document.documentElement;
        var nextIsWildcard = parts[0] === '';
        for (i=1; i<parts.length; i++) {
            if (el === null) {
                throw('Selector '+selector+' failed at segment '+i);
            }
            var next = parts[i].toUpperCase();
            if (next === '') {
                nextIsWildcard = true;
            } else {
                if (nextIsWildcard) {
                    el = el.getElementsByTagName(next)[0];
                } else {
                    var found = false;
                    for (var j=0; j<el.childNodes.length; j++) {
                        if (el.childNodes[j].tagName == next) {
                            el = el.childNodes[j];
                            found = true;
                            break;
                        } // fixme: no match
                    }
                    if (! found) {
                        throw('Nothing found for selector '+selector+' segment '+next);
                    }
                }
                nextIsWildcard = false;
            }
        }
        return el;
    } else {
        throw('Unknown selector: "' + selector + '"');
    }
}
