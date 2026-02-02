$(function () {
    var TYPEOPS = {
        // Every change to our supported JSON logic must be done
        // * in pretix.base.services.checkin
        // * in pretix.base.models.checkin
        // * in checkinrules.js
        // * in libpretixsync
        'product': {
            'inList': {
                'label': gettext('is one of'),
                'cardinality': 2,
            }
        },
        'variation': {
            'inList': {
                'label': gettext('is one of'),
                'cardinality': 2,
            }
        },
        'datetime': {
            'isBefore': {
                'label': gettext('is before'),
                'cardinality': 2,
            },
            'isAfter': {
                'label': gettext('is after'),
                'cardinality': 2,
            },
        },
        'int': {
            '<': {
                'label': '<',
                'cardinality': 2,
            },
            '<=': {
                'label': '≤',
                'cardinality': 2,
            },
            '>': {
                'label': '>',
                'cardinality': 2,
            },
            '>=': {
                'label': '≥',
                'cardinality': 2,
            },
            '==': {
                'label': '=',
                'cardinality': 2,
            },
            '!=': {
                'label': '≠',
                'cardinality': 2,
            },
        },
    };
    var VARS = {
        'product': {
            'label': gettext('Product'),
            'type': 'product',
        },
        'variation': {
            'label': gettext('Product variation'),
            'type': 'variation',
        },
        'now': {
            'label': gettext('Current date and time'),
            'type': 'datetime',
        },
        'entries_number': {
            'label': gettext('Number of previous entries'),
            'type': 'int',
        },
        'entries_today': {
            'label': gettext('Number of previous entries since midnight'),
            'type': 'int',
        },
        'entries_days': {
            'label': gettext('Number of days with a previous entry'),
            'type': 'int',
        },
    };

    Vue.component("datetimefield", {
        props: ["required", "value"],
        render: function (createElement) {
            return createElement('input', {
                class: 'form-control',
            });
        },
        mounted: function () {
            var vm = this;
            var multiple = this.multiple;
            $(this.$el)
                .datetimepicker(this.opts())
                .trigger("change")
                .on("dp.change", function (e) {
                    vm.$emit("input", $(this).data('DateTimePicker').date().toISOString());
                });
            if (!vm.value) {
                $(this.$el).data("DateTimePicker").viewDate(moment().hour(0).minute(0).second(0).millisecond(0));
            } else {
                $(this.$el).data("DateTimePicker").date(moment(vm.value));
            }
        },
        methods: {
            opts: function () {
                return {
                    format: $("body").attr("data-datetimeformat"),
                    locale: $("body").attr("data-datetimelocale"),
                    useCurrent: false,
                    showClear: this.required,
                    icons: {
                        time: 'fa fa-clock-o',
                        date: 'fa fa-calendar',
                        up: 'fa fa-chevron-up',
                        down: 'fa fa-chevron-down',
                        previous: 'fa fa-chevron-left',
                        next: 'fa fa-chevron-right',
                        today: 'fa fa-screenshot',
                        clear: 'fa fa-trash',
                        close: 'fa fa-remove'
                    }
                };
            }
        },
        watch: {
            value: function (val) {
                $(this.$el).data('DateTimePicker').date(moment(val));
            },
        },
        destroyed: function () {
            $(this.$el)
                .off()
                .datetimepicker("destroy");
        }
    });

    Vue.component("lookup-select2", {
        props: ["required", "value", "placeholder", "url", "multiple"],
        render: function (createElement) {
            return createElement('select', this.$slots.default);
        },
        mounted: function () {
            var vm = this;
            var multiple = this.multiple;
            $(this.$el)
                .select2(this.opts())
                .val(this.value || "") //set value to empty string if this.value is not valid
                .trigger("change")
                // emit event on change.
                .on("change", function (e) {
                    vm.$emit("input", $(this).select2('data'));
                });
            if (vm.value) {
                for (var i = 0; i < vm.value["objectList"].length; i++) {
                    var option = new Option(vm.value["objectList"][i]["lookup"][2], vm.value["objectList"][i]["lookup"][1], true, true);
                    $(vm.$el).append(option);
                }
            }
            $(vm.$el).trigger("change");
        },
        methods: {
            opts: function () {
                return {
                    theme: "bootstrap",
                    delay: 100,
                    width: '100%',
                    multiple: true,
                    allowClear: this.required,
                    language: $("body").attr("data-select2-locale"),
                    ajax: {
                        url: this.url,
                        data: function (params) {
                            return {
                                query: params.term,
                                page: params.page || 1
                            }
                        }
                    },
                    templateResult: function (res) {
                        if (!res.id) {
                            return res.text;
                        }
                        var $ret = $("<span>").append(
                            $("<span>").addClass("primary").append($("<div>").text(res.text).html())
                        );
                        return $ret;
                    },
                };
            }
        },
        watch: {
            placeholder: function (val) {
                $(this.$el).empty().select2(this.opts());
                this.build();
            },
            required: function (val) {
                $(this.$el).empty().select2(this.opts());
                this.build();
            },
            url: function (val) {
                $(this.$el).empty().select2(this.opts());
                this.build();
            },
        },
        destroyed: function () {
            $(this.$el)
                .off()
                .select2("destroy");
        }
    });

    Vue.component('checkin-rule', {
        render: function (createElement) {
            var children = [];

            // Button group
            var buttons = [];
            buttons.push(createElement('button', {
                attrs: { type: 'button' },
                class: 'checkin-rule-remove btn btn-xs btn-default',
                on: { click: function(e) { e.preventDefault(); this.wrapWithOR(); }.bind(this) }
            }, 'OR'));
            buttons.push(createElement('button', {
                attrs: { type: 'button' },
                class: 'checkin-rule-remove btn btn-xs btn-default',
                on: { click: function(e) { e.preventDefault(); this.wrapWithAND(); }.bind(this) }
            }, 'AND'));
            if (this.operands && this.operands.length == 1 && (this.operator === 'or' || this.operator == 'and')) {
                buttons.push(createElement('button', {
                    attrs: { type: 'button' },
                    class: 'checkin-rule-remove btn btn-xs btn-default',
                    on: { click: function(e) { e.preventDefault(); this.cutOut(); }.bind(this) }
                }, [createElement('span', { class: 'fa fa-cut' })]));
            }
            if (this.level > 0) {
                buttons.push(createElement('button', {
                    attrs: { type: 'button' },
                    class: 'checkin-rule-remove btn btn-xs btn-default',
                    on: { click: function(e) { e.preventDefault(); this.remove(); }.bind(this) }
                }, [createElement('span', { class: 'fa fa-trash' })]));
            }
            children.push(createElement('div', { class: 'btn-group pull-right' }, buttons));

            // Variable select
            var varOptions = [
                createElement('option', { domProps: { value: 'and' } }, gettext('All of the conditions below (AND)')),
                createElement('option', { domProps: { value: 'or' } }, gettext('At least one of the conditions below (OR)'))
            ];
            for (var name in this.vars) {
                var v = this.vars[name];
                varOptions.push(createElement('option', { domProps: { value: name } }, v.label));
            }
            children.push(createElement('select', {
                class: 'form-control',
                attrs: { required: true },
                domProps: { value: this.variable },
                on: { input: this.setVariable }
            }, varOptions));
            children.push(' ');

            // Operator select
            if (this.operator !== 'or' && this.operator !== 'and') {
                var opOptions = [createElement('option')];
                for (var name in this.operators) {
                    var v = this.operators[name];
                    opOptions.push(createElement('option', { domProps: { value: name } }, v.label));
                }
                children.push(createElement('select', {
                    class: 'form-control',
                    attrs: { required: true },
                    domProps: { value: this.operator },
                    on: { input: this.setOperator }
                }, opOptions));
                children.push(' ');
            }

            // Time type select
            if (this.vartype == 'datetime') {
                var timeOptions = [
                    createElement('option', { domProps: { value: 'date_from' } }, gettext('Event start')),
                    createElement('option', { domProps: { value: 'date_to' } }, gettext('Event end')),
                    createElement('option', { domProps: { value: 'date_admission' } }, gettext('Event admission')),
                    createElement('option', { domProps: { value: 'custom' } }, gettext('custom time'))
                ];
                children.push(createElement('select', {
                    class: 'form-control',
                    attrs: { required: true },
                    domProps: { value: this.timeType },
                    on: { input: this.setTimeType }
                }, timeOptions));
                children.push(' ');
            }

            // DateTime field
            if (this.vartype == 'datetime' && this.timeType == 'custom') {
                children.push(createElement('datetimefield', {
                    props: { value: this.timeValue },
                    on: { input: this.setTimeValue }
                }));
            }

            // Tolerance input
            if (this.vartype == 'datetime' && this.timeType && this.timeType != 'custom') {
                children.push(createElement('input', {
                    class: 'form-control',
                    attrs: { required: true, type: 'number', placeholder: gettext('Tolerance (minutes)') },
                    domProps: { value: this.timeTolerance },
                    on: { input: this.setTimeTolerance }
                }));
            }

            // Int input
            if (this.vartype == 'int' && this.cardinality > 1) {
                children.push(createElement('input', {
                    class: 'form-control',
                    attrs: { required: true, type: 'number' },
                    domProps: { value: this.rightoperand },
                    on: { input: this.setRightOperandNumber }
                }));
            }

            // Product Select
            if (this.vartype == 'product' && this.operator == 'inList') {
                children.push(createElement('lookup-select2', {
                    attrs: { required: true },
                    props: {
                        multiple: true,
                        value: this.rightoperand,
                        url: this.productSelectURL
                    },
                    on: { input: this.setRightOperandProductList }
                }));
            }

            // Variation Select
            if (this.vartype == 'variation' && this.operator == 'inList') {
                children.push(createElement('lookup-select2', {
                    attrs: { required: true },
                    props: {
                        multiple: true,
                        value: this.rightoperand,
                        url: this.variationSelectURL
                    },
                    on: { input: this.setRightOperandVariationList }
                }));
            }

            // Child rules (recursive)
            if (this.operator === 'or' || this.operator === 'and') {
                var childRulesNodes = [];
                if (this.operands) {
                    this.operands.forEach(function(op, opi) {
                        if (typeof op === 'object') {
                            childRulesNodes.push(createElement('div', [
                                createElement('checkin-rule', {
                                    props: {
                                        rule: op,
                                        index: opi,
                                        level: this.level + 1
                                    }
                                })
                            ]));
                        }
                    }.bind(this));
                }
                
                childRulesNodes.push(createElement('button', {
                    attrs: { type: 'button' },
                    class: 'checkin-rule-addchild btn btn-xs btn-default',
                    on: { click: function(e) { e.preventDefault(); this.addOperand(); }.bind(this) }
                }, [
                    createElement('span', { class: 'fa fa-plus-circle' }),
                    ' ' + gettext('Add condition')
                ]));

                children.push(createElement('div', { class: 'checkin-rule-childrules' }, childRulesNodes));
            }

            return createElement('div', { class: this.classObject }, children);
        },
        computed: {
            variable: function () {
                var op = this.operator;
                if (op === "and" || op === "or") {
                    return op;
                } else if (this.rule[op] && this.rule[op][0]) {
                    return this.rule[op][0]["var"];
                } else {
                    return null;
                }
            },
            rightoperand: function () {
                var op = this.operator;
                if (op === "and" || op === "or") {
                    return null;
                } else if (this.rule[op] && typeof this.rule[op][1] !== "undefined") {
                    return this.rule[op][1];
                } else {
                    return null;
                }
            },
            operator: function () {
                return Object.keys(this.rule)[0];
            },
            operands: function () {
                return this.rule[this.operator];
            },
            classObject: function () {
                var c = {
                    'checkin-rule': true
                };
                c['checkin-rule-' + this.variable] = true;
                return c;
            },
            vartype: function () {
                if (this.variable && VARS[this.variable]) {
                    return VARS[this.variable]['type'];
                }
            },
            timeType: function () {
                if (this.rightoperand && this.rightoperand['buildTime']) {
                    return this.rightoperand['buildTime'][0];
                }
            },
            timeTolerance: function () {
                var op = this.operator;
                if ((op === "isBefore" || op === "isAfter") && this.rule[op] && typeof this.rule[op][2] !== "undefined") {
                    return this.rule[op][2];
                } else {
                    return null;
                }
            },
            timeValue: function () {
                if (this.rightoperand && this.rightoperand['buildTime']) {
                    return this.rightoperand['buildTime'][1];
                }
            },
            cardinality: function () {
                if (this.vartype && TYPEOPS[this.vartype] && TYPEOPS[this.vartype][this.operator]) {
                    return TYPEOPS[this.vartype][this.operator]['cardinality'];
                }
            },
            operators: function () {
                return TYPEOPS[this.vartype];
            },
            productSelectURL: function () {
                return $("#product-select2").text();
            },
            variationSelectURL: function () {
                return $("#variations-select2").text();
            },
            vars: function () {
                return VARS;
            },
        },
        methods: {
            setVariable: function (event) {
                var current_op = Object.keys(this.rule)[0];
                var current_val = this.rule[current_op];

                if (event.target.value === "and" || event.target.value === "or") {
                    if (current_val[0] && current_val[0]["var"]) {
                        current_val = [];
                    }
                    this.$set(this.rule, event.target.value, current_val);
                    this.$delete(this.rule, current_op);
                } else {
                    if (current_val !== "and" && current_val !== "or" && current_val[0] && VARS[event.target.value]['type'] === this.vartype) {
                        this.$set(this.rule[current_op][0], "var", event.target.value);
                    } else {
                        this.$delete(this.rule, current_op);
                        this.$set(this.rule, "!!", [{"var": event.target.value}]);
                    }
                }
            },
            setOperator: function (event) {
                var current_op = Object.keys(this.rule)[0];
                var current_val = this.rule[current_op];
                this.$delete(this.rule, current_op);
                this.$set(this.rule, event.target.value, current_val);
            },
            setRightOperandNumber: function (event) {
                if (this.rule[this.operator].length === 1) {
                    this.rule[this.operator].push(parseInt(event.target.value));
                } else {
                    this.$set(this.rule[this.operator], 1, parseInt(event.target.value));
                }
            },
            setTimeTolerance: function (event) {
                if (this.rule[this.operator].length === 2) {
                    this.rule[this.operator].push(parseInt(event.target.value));
                } else {
                    this.$set(this.rule[this.operator], 2, parseInt(event.target.value));
                }
            },
            setTimeType: function (event) {
                var time = {
                    "buildTime": [event.target.value]
                };
                if (this.rule[this.operator].length === 1) {
                    this.rule[this.operator].push(time);
                } else {
                    this.$set(this.rule[this.operator], 1, time);
                }
                if (event.target.value === "custom") {
                    this.$set(this.rule[this.operator], 2, 0);
                }
            },
            setTimeValue: function (val) {
                console.log(val);
                this.$set(this.rule[this.operator][1]["buildTime"], 1, val);
            },
            setRightOperandProductList: function (val) {
                var products = {
                    "objectList": []
                };
                for (var i = 0; i < val.length; i++) {
                    products["objectList"].push({
                        "lookup": [
                            "product",
                            val[i].id,
                            val[i].text
                        ]
                    });
                }
                if (this.rule[this.operator].length === 1) {
                    this.rule[this.operator].push(products);
                } else {
                    this.$set(this.rule[this.operator], 1, products);
                }
            },
            setRightOperandVariationList: function (val) {
                var products = {
                    "objectList": []
                };
                for (var i = 0; i < val.length; i++) {
                    products["objectList"].push({
                        "lookup": [
                            "variation",
                            val[i].id,
                            val[i].text
                        ]
                    });
                }
                if (this.rule[this.operator].length === 1) {
                    this.rule[this.operator].push(products);
                } else {
                    this.$set(this.rule[this.operator], 1, products);
                }
            },
            addOperand: function () {
                this.rule[this.operator].push({"": []});
            },
            wrapWithOR: function () {
                var r = JSON.parse(JSON.stringify(this.rule));
                this.$delete(this.rule, this.operator);
                this.$set(this.rule, "or", [r]);
            },
            wrapWithAND: function () {
                var r = JSON.parse(JSON.stringify(this.rule));
                this.$delete(this.rule, this.operator);
                this.$set(this.rule, "and", [r]);
            },
            cutOut: function () {
                var cop = Object.keys(this.operands[0])[0];
                var r = this.operands[0][cop];
                this.$delete(this.rule, this.operator);
                this.$set(this.rule, cop, r);
            },
            remove: function () {
                this.$parent.rule[this.$parent.operator].splice(this.index, 1);
            },
        },
        props: {
            rule: Object,
            level: Number,
            index: Number,
        }
    });

    Vue.component('checkin-rules-editor', {
        render: function (createElement) {
            var children = [];
            if (this.hasRules) {
                children.push(createElement('checkin-rule', {
                    props: {
                        rule: this.$root.rules,
                        level: 0,
                        index: 0
                    }
                }));
            }
            if (!this.hasRules) {
                children.push(createElement('button', {
                    attrs: {
                        type: 'button'
                    },
                    class: 'checkin-rule-addchild btn btn-xs btn-default',
                    on: {
                        click: function (event) {
                            event.preventDefault();
                            this.addRule();
                        }.bind(this)
                    }
                }, [
                    createElement('span', { class: 'fa fa-plus-circle' }),
                    ' ' + gettext('Add condition')
                ]));
            }
            return createElement('div', { class: 'checkin-rules-editor' }, children);
        },
        computed: {
            hasRules: function () {
                return hasRules = !!Object.keys(this.$root.rules).length;
            }
        },
        methods: {
            addRule: function () {
                this.$set(this.$root.rules, "and", []);
            },
        },
    });

    var app = new Vue({
        el: '#rules-editor',
        data: function () {
            return {
                rules: {},
                hasRules: false,
            };
        },
        created: function () {
            this.rules = JSON.parse($("#id_rules").val());
        },
        watch: {
            rules: {
                deep: true,
                handler: function (newval) {
                    $("#id_rules").val(JSON.stringify(newval));
                }
            },
        }
    })
});
