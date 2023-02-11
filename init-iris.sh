export PATH=$PATH:~/.local/bin

cat <<EOF | iris session iris -U %SYS
do ##class(Security.Users).UnExpireUserPasswords("*")
set prop("Enabled")=1 
Do ##class(Security.Services).Modify("%Service_CallIn",.prop) 
halt
EOF
