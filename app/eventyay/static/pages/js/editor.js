/*global $, Quill*/
$(function () {
    var page_name = $('#content').data('page-name');
    var getContentTextarea = function (lang) {
        // Current page form uses text_<index> fields with language metadata.
        var currentSelector = 'textarea[name^="text_"][lang="' + lang + '"]';
        var $current = $(currentSelector);
        if ($current.length) {
            return $current.first();
        }

        // Fallback for legacy markup still using <page_name>_content_<index>.
        if (page_name) {
            var legacySelector = 'textarea[name^="' + page_name + '_content_"][lang="' + lang + '"]';
            var $legacy = $(legacySelector);
            if ($legacy.length) {
                return $legacy.first();
            }
        }

        return $();
    };

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

    $('#content ul.nav-tabs a').click(function (e) {
        e.preventDefault();
        $(this).tab('show');
    });


    var quills = {};
    $('.editor').each(function () {
        var language = $(this).attr("data-lng");
        var $contentInput = getContentTextarea(language);
        $(this).html($contentInput.length ? $contentInput.val() : "");
        quills[language] = new Quill($(this).get(0), {
            theme: 'snow',
            formats: [
                'bold', 'italic', 'link', 'strike', 'code', 'underline', 'script',
                'list', 'align', 'code-block', 'header', 'image'
            ],
            modules: {
                toolbar: [
                    [{'header': [3, 4, 5, false]}],
                    ['bold', 'italic', 'underline', 'strike'],
                    ['link'],
                    ['image'],
                    [{'align': []}],
                    [{'list': 'ordered'}, {'list': 'bullet'}],
                    [{'script': 'sub'}, {'script': 'super'}],
                    ['clean']
                ]
            }
        });
    });

    $('.editor').closest('form').submit(function () {
        $('.editor').each(function () {
            var language = $(this).attr("data-lng");
            var val = $(this).find('.ql-editor').html();
            var $contentInput = getContentTextarea(language);
            if ($contentInput.length) {
                $contentInput.val(val);
            }
        });
    });
});
