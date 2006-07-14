
var pu = null;  // Global object

function PageUpdater () {
    
    this.xmlurl = "../reports/requirementsclean.xml";
    this.xslurl = "../reports/requirementsreport.xsl";
    
    this.xmldoc = new MochiXML();
    this.xsldoc = new MochiXML();    
}

PageUpdater.prototype.init = function () {
    
    var d1 = this.xsldoc.loadURL(this.xslurl);
    var d2 = this.xmldoc.loadURL(this.xmlurl);
    
    d1.addCallback(bind(this.makeprocessor, this))    
    d2.addCallback(bind(this.dataLoaded, this));
    
}


PageUpdater.prototype.dataLoaded = function () {
    var log = getElement("log");
    log.firstChild.nodeValue = "Finished loading";
}


PageUpdater.prototype.makeprocessor = function () {
    this.processor = new XSLTProcessor();
    this.processor.importStylesheet(this.xsldoc.xmldoc);
}

PageUpdater.prototype.redraw = function (req) {
    
    var isIE = document.all && window.ActiveXObject && navigator.userAgent.toLowerCase().indexOf("msie") > -1  && navigator.userAgent.toLowerCase().indexOf("opera") == -1;
    var input = this.xmldoc.xmldoc.documentElement;
    var target = document.getElementById("content");
    //Sarissa.updateContentFromNode(input, target, this.processor, false);
    //return;
    var newDocument = this.processor.transformToDocument(input);
    if (isIE) {
        var newdiv = newDocument.documentElement;
        alert(newdiv.innerHTML);
    } else {
        var nn = document.importNode(newDocument.documentElement, true);
        //alert(Sarissa.serialize(nn).substring(0,100));
        //Sarissa.copyChildNodes(nn, target);
        target.innerHTML = nn.innerHTML;
    }
    
    return;
}

function clickCancel (e) {
    e.stop();
    var target = e.target();
    var reportname = target.getAttribute("href");
    pu.xmldoc.xmldoc.documentElement.setAttribute("view", reportname);
    pu.redraw();
    return false;
}


function redraw () {
    pu.redraw();
}

function main() {
    var linkbox = document.getElementById("links");
    var links = iter(linkbox.getElementsByTagName("a"));
    forEach(links, function cancelClick (link) {
        connect(link, "onclick", clickCancel)
    });

    pu = new PageUpdater();
    pu.init();
}

connect(window, "onload", main);