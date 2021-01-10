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
    $('#klipper-settings a:first').tab('show');
    function KlipperSettingsViewModel(parameters) {
        var self = this;
        self.settings = parameters[0];

        self.addMacro = function() {
           self.settings.settings.plugins.klipper.macros.push({
              name: 'Macro',
              macro: '',
              sidebar: true,
              tab: true
           });
        }

        self.addLine = function() {
         self.settings.settings.plugins.klipper.macros.push({
            name: 'HLine',
            macro: '',
            sidebar: true,
            tab: true
         });
        }
        
        self.removeMacro = function(macro) {
           self.settings.settings.plugins.klipper.macros.remove(macro);
        }
        
        self.moveMacroUp = function(macro) {
           self.moveItemUp(self.settings.settings.plugins.klipper.macros, macro)
        }
                
        self.moveMacroDown = function(macro) {
           self.moveItemDown(self.settings.settings.plugins.klipper.macros, macro)
        }
        
        self.addProbePoint = function() {
           self.settings.settings.plugins.klipper.probe.points.push(
              {
                 name: 'point-#',
                 x:0, y:0, z:0
              }
           );
        }
        
        self.removeProbePoint = function(point) {
           self.settings.settings.plugins.klipper.probe.points.remove(point);
        }
        
        self.moveProbePointUp = function(macro) {
           self.moveItemUp(self.settings.settings.plugins.klipper.probe.points, macro)
        }
                
        self.moveProbePointDown = function(macro) {
           self.moveItemDown(self.settings.settings.plugins.klipper.probe.points, macro)
        }
        
        self.moveItemDown = function(list, item) {
           var i = list().indexOf(item);
           if (i < list().length - 1) {
               var rawList = list();
              list.splice(i, 2, rawList[i + 1], rawList[i]);
           }
        }
        
        self.moveItemUp = function(list, item) {
           var i = list().indexOf(item);
           if (i > 0) {
              var rawList = list();
              list.splice(i-1, 2, rawList[i], rawList[i-1]);
           }
        }
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: KlipperSettingsViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_klipper"]
    });
});
