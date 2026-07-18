!macro customUnInstall
  ReadEnvStr $R0 "AETHER_REMOVE_PROFILE_DATA"
  StrCmp $R0 "1" remove_aether_profile_data
  IfSilent keep_aether_profile_data
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 \
    "Remove Aether profile data, governed memory, conversations, and receipts from this Windows account? Select No to keep them for reinstall or upgrade." \
    IDNO keep_aether_profile_data

  remove_aether_profile_data:
  RMDir /r "$APPDATA\${APP_FILENAME}\aether-state"
  !ifdef APP_PRODUCT_FILENAME
    RMDir /r "$APPDATA\${APP_PRODUCT_FILENAME}\aether-state"
  !endif
  !ifdef APP_PACKAGE_NAME
    RMDir /r "$APPDATA\${APP_PACKAGE_NAME}\aether-state"
  !endif

  keep_aether_profile_data:
!macroend
