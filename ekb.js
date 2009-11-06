	
function inserttext(selector, text)
{
    var obj = selector[0];
    if (obj.selectionStart != null)
    {
	var orig = selector.val();
	var s = obj.selectionStart;
	var e = obj.selectionEnd;
	var before = orig.substring(0, s);
	var after  = orig.substring(e, orig.length); 
	selector.val(before + text + after);
	obj.selectionStart = s;
	obj.selectionEnd = s + text.length;
	selector.focus();
    }
    else if (document.selection) // IE
    {
	selector.focus();
	var range = document.selection.createRange();
	range.text = text;
    }
}


function add_link(s)
{
    inserttext($("#markdown-text"), "\n![](" + s + ")\n");
}


var uploadt = null;


function upload_clicked()
{
    $('#uploadframe_div').html
	("<iframe name='uploadframe' id='uploadframe' style='display: none'>"
	 + "</iframe>");
    $('#uploadframe').load(upload_done);
    $('#uploadform').attr('target', 'uploadframe').submit();
    
    $('#uploads').append("<li style='display: none; list-style-type: none'>" +
			 "<b>Uploading...</b></li>");
    $('#uploads li:last').fadeIn(1000);
}


function upload_done()
{
    var last = $('#uploads li:last');
    var ret = $('#uploadframe').contents().text();
    var code = ret.substring(0, 1);
    var s = ret.substring(2, ret.length);
    if (code == "0") {
	setTimeout(function() {
	    last.html(s).append(" [<a href=''>insert</a>]</li>");
	    last.find('a').click(function() {
		add_link("/static/kbfiles/" + s);
		return false; 
	    });
	    $('#uploadform')[0].reset();
	}, 1000);
    } else {
	last.remove();
	$('#uploadframe').remove();
	alert(s);
	$('#uploadform')[0].reset();
    }
}
