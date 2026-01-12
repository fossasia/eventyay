<template>
  <input class="form-control" :required="required" />
</template>

<script>
export default {
  props: {
    required: Boolean,
    modelValue: String,
  },
  emits: ['update:modelValue'],
  mounted() {
    $(this.$el)
      .datetimepicker(this.opts())
      .trigger('change')
      .on('dp.change', () => {
        const val = $(this.$el).data('DateTimePicker').date().format('HH:mm:ss')
        this.$emit('update:modelValue', val)
      })

    if (!this.modelValue) {
      $(this.$el)
        .data('DateTimePicker')
        .viewDate(moment().hour(0).minute(0).second(0).millisecond(0))
    } else {
      $(this.$el).data('DateTimePicker').date(moment(this.modelValue))
    }
  },
  methods: {
    opts() {
      return {
        format: $('body').attr('data-timeformat'),
        locale: $('body').attr('data-datetimelocale'),
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
          close: 'fa fa-remove',
        },
      }
    },
  },
  watch: {
    modelValue(val) {
      if (val !== undefined) {
        $(this.$el).data('DateTimePicker').date(moment(val))
      }
    },
  },
  unmounted() {
    $(this.$el).off().datetimepicker('destroy')
  },
}
</script>
