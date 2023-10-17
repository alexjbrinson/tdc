from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtWidgets import QDialog, QApplication, QFileDialog
import sys
import pickle


#np.set_printoptions(threshold=np.inf)

qtCreatorFile = "TDCSettingsDialogWindow.ui" # Enter file here.
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

#TODO: send stop command to TDC before attempting re-connect
class SettingsWindow(QtWidgets.QWidget, Ui_MainWindow):
  submitClicked=QtCore.pyqtSignal(dict) #<--- this is the setting window's signal
  def __init__(self, settingDic={}):
    print('settings window opened')
    QtWidgets.QMainWindow.__init__(self); Ui_MainWindow.__init__(self)
    self.setupUi(self)
    self.setWindowTitle('TDC Settings')
    if settingDic=={}:
      self.settingDic={'int_time':500,
                     'mode':'NIM',
                     'threshold':-0.25,
                     'path':'./'}
    else: 
      print('ayyy',settingDic)
      self.settingDic=settingDic

    self.int_time=self.settingDic['int_time'] ; self.mode = self.settingDic['mode']
    self.threshold=self.settingDic['threshold']; self.scanDirectory=self.settingDic['path']

    self.scanDirectoryLabel.setText(self.scanDirectory)
    self.ttlRadioButton.setChecked(True) if self.mode=='TTL' else self.nimRadioButton.setChecked(True) 
    self.thresholdDoubleSpinBox.setValue(self.threshold)
    self.integrationTimeLineEdit.setText(str(self.int_time))
    
    self.browseButton.clicked.connect(self.selectDirectory)
    self.ttlRadioButton.clicked.connect(self.setTTL)
    self.nimRadioButton.clicked.connect(self.setNIM)
    #super(MyApp, self).__init__()
    
    #self.confirm()
    self.cancellationButton.clicked.connect(self.cancel)
    self.confirmationButton.clicked.connect(self.confirm)

  def selectDirectory(self):
    file = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
    self.scanDirectory=file
    self.scanDirectoryLabel.setText(self.scanDirectory)

  def setTTL(self):self.mode='TTL'; self.thresholdDoubleSpinBox.setValue(1.8) #these can be overwritten, but this is probably a better setpoint than whatever the previous nim threshold was
  def setNIM(self):self.mode='NIM'; self.thresholdDoubleSpinBox.setValue(-.25) #these can be overwritten, but this is probably a better setpoint than whatever the previous ttl threshold was

  def cancel(self):
    #print('cancel clicked')
    #self.submitClicked.emit(self.settingDic) #if I don't update the setting dictionary, I'll just return kwarg input / preset values
    self.close()

  def confirm(self):
    try:
      t=int(self.integrationTimeLineEdit.text())
      if t<0 or t>50_000:
        self.errorFeedbackLabel.setText('integration time must be an integer between 0 and 50,000. SMH')
        return()
      else: self.int_time=t
    except:self.errorFeedbackLabel.setText('integration time must be an integer between 0 and 50,000. SMH'); return()
    self.threshold=self.thresholdDoubleSpinBox.value()
    self.settingDic={'int_time':self.int_time,
                     'mode':self.mode,
                     'threshold':self.threshold,
                     'path':self.scanDirectory}
    self.errorFeedbackLabel.setText('Whee')
    self.submitClicked.emit(self.settingDic)
    self.close()

if __name__ == "__main__":
  app = QtWidgets.QApplication(sys.argv)
  window = SettingsWindow()
  app.aboutToQuit.connect(window.cancel) #TODO: write safeExit function
  window.show()
  sys.exit(app.exec_())