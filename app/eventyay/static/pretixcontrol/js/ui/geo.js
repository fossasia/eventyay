/*globals $*/

$(function () {
    const DEFAULT_ZOOM = 15;

    function cleanup(l) {
        return $.trim(l.replace(/\n/g, ", "));
    }
    $(".geodata-section").each(function () {
        // Geocoding
        var $geoLabel = $(".geodata-group label.control-label", this).first();
        var $fallbackLabel = $geoLabel.length ? $geoLabel : $("label", this).first();
        var $notifications = $(".geodata-autoupdate", this).detach();
        var $lat = $("input[name$=geo_lat]", this).first();
        var $lon = $("input[name$=geo_lon]", this).first();
        var lat;
        var lon;
        var $updateButton = $notifications.find("[data-action=update]");
        var $savePinButton = $notifications.find("[data-action=save-pin]");
        var $resetPinButton = $notifications.find("[data-action=reset-pin]");
        var $form = $(this).closest("form");
        var $location = $("textarea[lang=en], input[lang=en]", this).first();
        if (!$location.length) $location = $("textarea, input[type=text]", this).first();

        if (!$lat.length || !$lon.length || !$location.length) {
            return;
        }

        var debounceLoad, debounceLatLonChange, delayUpdateDismissal;
        var touched = $lat.val() !== "";
        var xhr;
        var lastLocation = null;
        var pendingPin = null;

        function getpoint() {
            if ($lat.val() !== "" && $lon.val() !== "" && !isNaN(parseFloat($lat.val())) && !isNaN(parseFloat($lon.val()))) {
                var p = [parseFloat($lat.val().replace(",", ".")), parseFloat($lon.val().replace(",", "."))];
                // Clip to valid ranges. Very invalid lon/lat values can even lead to browser crashes in leaflet apparently
                if (p[0] < -90) p[0] = -90;
                if (p[0] > 90) p[0] = 90;
                if (p[1] < -180) p[1] = -180;
                if (p[1] > 180) p[1] = 180;
                return p;
            }
            return null;
        }

        function showUpdatedConfirmation() {
            $notifications.attr("data-notify", "updated");
            window.clearTimeout(delayUpdateDismissal);
            delayUpdateDismissal = window.setTimeout(function() {
                if ($notifications.attr("data-notify") === "updated") $notifications.attr("data-notify", "");
            }, 2500);
        }

        function load(force) {
            window.clearTimeout(debounceLoad);
            if (xhr) {
                xhr.abort();
                xhr = null;
            }

            var q = cleanup($location.val());
            if (q === "" || (!force && q === lastLocation)) return;

            lastLocation = q;
            $notifications.attr("data-notify", "loading");

            xhr = $.getJSON('/control/geocode/?q=' + encodeURIComponent(q), function (res) {
                if (!res.results || !res.results.length) {
                    $notifications.attr("data-notify", "error");
                    return;
                }

                lat = res.results[0].lat;
                lon = res.results[0].lon;
                if ($lat.val() == lat && $lon.val() == lon) {
                    $notifications.attr("data-notify", "");
                }
                else if (touched) {
                    $notifications.attr("data-notify", "confirm");
                }
                else {
                    $notifications.attr("data-notify", "");
                    $lat.val(lat);
                    $lon.val(lon);
                    center(DEFAULT_ZOOM);
                }
            }).fail(function (jqXHR, textStatus, errorThrown) {
                if (textStatus !== 'abort') {
                    $notifications.attr("data-notify", "error");
                }
            });
        }

        $lat.add($lon).change(function () {
            if (this.value !== "") touched = true;
            pendingPin = null;
            if ($notifications.attr("data-notify") === "confirm-pin") {
                $notifications.attr("data-notify", "");
            }
            center(DEFAULT_ZOOM);
        }).keyup(function () {
            window.clearTimeout(debounceLatLonChange);
            debounceLatLonChange = window.setTimeout(center, 300);
        });

        $location.change(function () {
            load(false);
        });
        $location.keyup(function () {
            window.clearTimeout(debounceLoad);
            debounceLoad = window.setTimeout(function () {
                load(false);
            }, 1000);
            if (($notifications.attr("data-notify") === "confirm" || $notifications.attr("data-notify") === "confirm-pin") && lastLocation !== cleanup(this.value)) {
                $notifications.attr("data-notify", "");
            }
        });

        $updateButton.click(function() {
            $lat.val(lat);
            $lon.val(lon).trigger("change");// change-event is needed by bulk-edit
            touched = false;
            center(DEFAULT_ZOOM);
            pendingPin = null;
            showUpdatedConfirmation();
        });

        $savePinButton.click(function () {
            if (!pendingPin) {
                return;
            }
            $lat.val(pendingPin.lat);
            $lon.val(pendingPin.lon).trigger("change");
            pendingPin = null;
            touched = true;
            center(DEFAULT_ZOOM);
            showUpdatedConfirmation();
        });

        $resetPinButton.click(function () {
            pendingPin = null;
            center(DEFAULT_ZOOM);
            $notifications.attr("data-notify", "");
        });

        if ($form.length) {
            $form.on("submit", function () {
                if (!pendingPin) {
                    return;
                }
                $lat.val(pendingPin.lat);
                $lon.val(pendingPin.lon);
                pendingPin = null;
            });
        }

        // Map
        var $grp = $(".geodata-group", this);
        var tiles = $grp.attr("data-tiles");
        var attrib = $grp.attr("data-attrib");
        
        var center;

        if (tiles) {
            var $map = $("<div>");
            var $mapWrap = $("<div>").addClass("col-md-9 col-md-offset-3").append($map);
            if ($notifications.length) {
                $mapWrap.append($notifications);
            }
            $grp.append($mapWrap);
            var map = L.map($map.get(0));
            L.tileLayer(tiles, {
                attribution: attrib,
                maxZoom: 18,
            }).addTo(map);

            var marker = L.marker(getpoint() || [0, 0], {
                draggable: true,
                icon: L.icon({
                    iconUrl: $grp.attr("data-icon"),
                    shadowUrl: $grp.attr("data-shadow"),
                    iconSize: [25, 41],
                    iconAnchor: [12, 41],
                    popupAnchor: [1, -34],
                    tooltipAnchor: [16, -28],
                    shadowSize: [41, 41]
                })
            });
            
            var point = getpoint();
            if (point) {
                marker.addTo(map);
            }

            marker.on("dragend", function (event) {
                var position = marker.getLatLng();
                marker.setLatLng(position, {
                    draggable: true
                }).bindPopup(position.lat.toFixed(7) + ", " + position.lng.toFixed(7)).update();
                pendingPin = {
                    lat: position.lat.toFixed(7),
                    lon: position.lng.toFixed(7)
                };
                touched = true;
                $notifications.attr("data-notify", "confirm-pin");
            });

            center = function(zoom) {
                var p = getpoint();
                if (p) {
                    if (zoom) {
                        map.setView(p, zoom);
                    } else {
                        map.panTo(p);
                    }
                    if (!map.hasLayer(marker)) {
                        marker.addTo(map);
                    }
                    marker.setLatLng(p, {
                        draggable: true
                    }).bindPopup(p[0].toFixed(7) + ", " + p[1].toFixed(7)).update();
                } else {
                    map.fitWorld();
                    if (map.hasLayer(marker)) {
                        map.removeLayer(marker);
                    }
                }
            };

            center(DEFAULT_ZOOM);
        } else {
            if ($notifications.length) {
                $notifications.appendTo($fallbackLabel);
            }
            center = function(zoom) {};
        }

        if (!getpoint() && cleanup($location.val()) !== "") {
            load(true);
        }

    });
});
