document.addEventListener('DOMContentLoaded', function() {
    var depQuestion = document.getElementById('id_dependency_question');
    var depValues = document.getElementById('id_dependency_values');
    var depContainer = document.querySelector('fieldset[data-options-url-base]');
    var configEl = document.getElementById('dependency-question-config');
    
    if (!depQuestion || !depValues || !depContainer || !configEl) {
        return;
    }

    var savedValuesEl = document.getElementById('dependency_value_val');
    var savedValues = [];
    try {
        savedValues = JSON.parse(savedValuesEl ? savedValuesEl.textContent : '[]');
    } catch (error) {
        console.error('Failed to parse saved dependency values JSON', error);
        savedValues = [];
    }
    
    var yesLabel = configEl.getAttribute('data-yes-label') || 'Yes';
    var noLabel = configEl.getAttribute('data-no-label') || 'No';
    
    function removeLoadingIndicator() {
        var indicators = depValues.parentElement.querySelectorAll('.loading-indicator');
        indicators.forEach(function(el) { el.remove(); });
    }
    
    function showLoadingIndicator() {
        var indicator = document.createElement('div');
        indicator.className = 'help-block loading-indicator';
        indicator.innerHTML = '<span class="fa fa-cog fa-spin"></span>';
        depValues.parentElement.appendChild(indicator);
    }
    
    function updateDependencyOptions() {
        removeLoadingIndicator();
        depValues.innerHTML = '';
        depValues.required = false;

        var selectedValue = depQuestion.value;
        if (!selectedValue) {
            return;
        }

        depValues.required = true;
        showLoadingIndicator();

        var optionsUrlTemplate = depContainer.getAttribute('data-options-url-base');
        if (!optionsUrlTemplate) {
            removeLoadingIndicator();
            return;
        }
        var ajaxUrl = optionsUrlTemplate.replace('/0/', '/' + selectedValue + '/');
        
        fetch(ajaxUrl)
            .then(function(response) {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(function(data) {
                if (data.variant === 'boolean') {
                    var optYes = document.createElement('option');
                    optYes.value = 'True';
                    optYes.textContent = yesLabel;
                    depValues.appendChild(optYes);
                    
                    var optNo = document.createElement('option');
                    optNo.value = 'False';
                    optNo.textContent = noLabel;
                    depValues.appendChild(optNo);
                } else if (data.options) {
                    data.options.forEach(function(opt) {
                        var option = document.createElement('option');
                        option.value = opt.id;
                        option.textContent = opt.answer;
                        depValues.appendChild(option);
                    });
                }
                
                if (savedValues && savedValues.length > 0) {
                    Array.from(depValues.options).forEach(function(opt) {
                        if (savedValues.indexOf(opt.value) !== -1) {
                            opt.selected = true;
                        }
                    });
                }
                
                removeLoadingIndicator();
            })
            .catch(function(error) {
                console.error('Failed to load dependency options', error);
                removeLoadingIndicator();
            });
    }

    updateDependencyOptions();
    depQuestion.addEventListener('change', updateDependencyOptions);
});
