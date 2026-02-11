/*global $, Quill*/
$(function () {
    var slug_generated = !$("form[data-id]").attr("data-id");
    $('#id_slug').on("keydown keyup keypress", function () {
        slug_generated = false;
    });
    $('input[id^=id_title_]').on("keydown keyup keypress change", function () {
        if (slug_generated) {
            var title = $('input[id^=id_title_]').filter(function () {
                return !!this.value;
            }).first().val();  // First non-empty language
            if (typeof title === "undefined") {
                return;
            }
            var slug = title.toLowerCase()
                .replace(/\s+/g, '-')
                .replace(/[^\w\-]+/g, '')
                .replace(/\-\-+/g, '-')
                .replace(/^-+/, '')
                .replace(/-+$/, '')
                .substr(0, 150);
            $('#id_slug').val(slug);
        }
    });


    var textareas = $('#form-text-container').find('textarea');
    var quills = {};
    $('.editor').each(function (index) {
        var $editor = $(this);
        var $textarea = textareas.eq(index);

        if ($textarea.length === 0) {
            return;
        }

        var quill = new Quill($editor.get(0), {
            theme: 'snow',
            formats: [
                'bold', 'italic', 'link', 'strike', 'code', 'underline', 'script',
                'list', 'align', 'code-block', 'header', 'image'
            ],
            modules: {
                toolbar: [
                    [{ header: [3, 4, 5, false] }],
                    ['bold', 'italic', 'underline', 'strike'],
                    ['link'],
                    ['image'],
                    [{ align: [] }],
                    [{ list: 'ordered' }, { list: 'bullet' }],
                    [{ script: 'sub' }, { script: 'super' }],
                    ['clean']
                ]
            }
        });

        quill.clipboard.dangerouslyPasteHTML($textarea.val() || '');

        quills[index] = {
            quill: quill,
            textarea: $textarea
        };
    });

    $('form').on('submit', function () {
        Object.values(quills).forEach(function (item) {
            item.textarea.val(item.quill.root.innerHTML);
        });
    });
});