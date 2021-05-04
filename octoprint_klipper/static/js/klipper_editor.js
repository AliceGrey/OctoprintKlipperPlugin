// <Octoprint Klipper Plugin>

// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as
// published by the Free Software Foundation, either version 3 of the
// License, or (at your option) any later version.

// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.

// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

$(function() {
   function KlipperEditorViewModel(parameters) {
      var self = this;
      self.loginState = parameters[0];
      self.klipperViewModel = parameters[1];

      self.header = OctoPrint.getRequestHeaders({
         "content-type": "application/json",
         "cache-control": "no-cache"
      });

      self.apiUrl = OctoPrint.getSimpleApiUrl("klipper");

      self.availableConfigFiles = ko.observableArray();
      self.configFile = ko.observable();
      self.status = ko.observable();
      self.spinnerDialog;

      self.onStartup = function() {
         self.spinnerDialog = $("#klipper_editor_spinner");

         if(self.loginState.loggedIn()) {
            self.requestConfigfiles();
         }
      }

      self.onUserLoggedIn = function(user) {
         self.requestConfigfiles();
      }

      self.showSpinner = function(showDialog) {
         if (showDialog) {
            self.spinnerDialog.modal({
               show: true,
               keyboard: false,
               backdrop: "static"
            });
         } else {
            self.spinnerDialog.modal("hide");
         }
      }

      // initialize list helper
      self.fileList = new ItemListHelper(
         "ConfigFiles",
         {
            name: function (a, b) {
               // sorts ascending
               if (a["name"].toLocaleLowerCase() < b["name"].toLocaleLowerCase())
                     return -1;
               if (a["name"].toLocaleLowerCase() > b["name"].toLocaleLowerCase())
                     return 1;
               return 0;
            },
            date: function (a, b) {
               // sorts descending
               if (a["date"] > b["date"]) return -1;
               if (a["date"] < b["date"]) return 1;
               return 0;
            },
            size: function (a, b) {
               // sorts descending
               if (a["bytes"] > b["bytes"]) return -1;
               if (a["bytes"] < b["bytes"]) return 1;
               return 0;
            }
         },
         {},
         "name",
         [],
         [],
         0
      );

      self.requestConfigfiles = function() {
         var settings = {
            "crossDomain": true,
            "url": self.apiUrl,
            "method": "POST",
            "headers": self.header,
            "processData": false,
            "dataType": "json",
            "data": JSON.stringify({
               command: "requestConfigfiles"
            })
         }
         //self.showSpinner(true);

         $.ajax(settings).done(function (response) {
            self.showSpinner(false);
            // files
            self.fileList.updateItems(response["data"]);
            self.fileList.resetPage();
         });
      }

      self.removeFile = function (filename) {
         if (!self.klipperViewModel.hasRight("CONFIG")) return;
         var perform = function () {
            var settings = {
               "crossDomain": true,
               "url": self.apiUrl,
               "method": "POST",
               "headers": self.header,
               "processData": false,
               "dataType": "json",
               "data": JSON.stringify({
                  command: "deleteConfigfile",
                  file: filename
               })
            }
            //self.showSpinner(true);

            $.ajax(settings)
               .done(function (response) {
                  // files
                  self.fileList.updateItems(response["data"]);
                  self.fileList.resetPage();
               })
               .fail(function (jqXHR) {
                  var html =
                     "<p>" +
                     _.sprintf(
                        gettext(
                              "Failed to remove config %(name)s.</p><p>Please consult octoprint.log for details.</p>"
                        ),
                        {name: _.escape(filename)}
                     );
                  html += pnotifyAdditionalInfo(
                     '<pre style="overflow: auto">' +
                        _.escape(jqXHR.responseText) +
                        "</pre>"
                  );
                  new PNotify({
                     title: gettext("Could not remove config"),
                     text: html,
                     type: "error",
                     hide: false
                  });
               });
         }

         showConfirmationDialog(
            _.sprintf(gettext('You are about to delete timelapse file "%(name)s".'), {
                  name: _.escape(filename)
            }),
            perform
         );
      }
   }

OCTOPRINT_VIEWMODELS.push({
      construct: KlipperEditorViewModel,
      dependencies: ["loginStateViewModel",
                     "klipperViewModel"
                  ],
      elements: ["#klipper_editor_dialog"]
   });
});
