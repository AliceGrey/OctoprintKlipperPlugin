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
         self.listConfigFiles();
      }
   }

   self.onUserLoggedIn = function(user) {
      self.listConfigFiles();
   }

   self.listConfigFiles = function() {
      var settings = {
        "crossDomain": true,
        "url": self.apiUrl,
        "method": "POST",
        "headers": self.header,
        "processData": false,
        "dataType": "json",
        "data": JSON.stringify({command: "listConfigFiles"})
      }

      $.ajax(settings).done(function (response) {
         self.availableConfigFiles.removeAll();
         self.availableConfigFiles(response["data"]);
      });
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

   self.convertTime = function(val) {
      return moment(val, "X");
   }

   self.loadData = function() {
      var settings = {
        "crossDomain": true,
        "url": self.apiUrl,
        "method": "POST",
        "headers": self.header,
        "processData": false,
        "dataType": "json",
        "data": JSON.stringify(
           {
              command: "getConfig",
              ConfigFile: self.configFile()
           }
        )
      };

      self.showSpinner(true);

      $.ajax(settings).done(function (response) {
         self.status("")
         self.showSpinner(false);
      });
   }
}

OCTOPRINT_VIEWMODELS.push({
      construct: KlipperEditorViewModel,
      dependencies: ["loginStateViewModel"],
      elements: ["#klipper_editor_dialog"]
   });
});
