#!/usr/bin/env bash
 
#########################################################################
#########################################################################
#
# This shell script checks for free disk space for defined disks and send
# email alert based on threshold defined for warning and critical emails 
#
# Warning and critical thresholds can be passed as command-line parameters
# The command can be run as:
#
# "bash /path/to/script.sh -w 20 -c 10 -d /dev/sda1 -d /"
#
# The above script will check free space on /dev/sda1 and disk
# mounted on the root (/) file system. The script will send a Warning alert
# if free space is less than 20% of available space and a Critical alert
# will be sent if free space is less than 10%. 
#
#   Default warning alert threshold: 20%
#   Default critical alert threshold: 10%
#   Default disk to check: /
#
#########################################################################
#########################################################################
 
### initializing variables
__dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

. ${__dir}/eventyay_common.sh


## To enable email notification set ENABLE_EMAIL_ALERT to 1
ENABLE_EMAIL_ALERT=1
NOTIFICATION_EMAIL=$MANAGEMENT_EMAIL
 
## Uncomment and set a custom hostname, default uses the system's hostname
#HOSTNAME="web-server1"
 
 
## Other variables required for the script
 
THRESHOLD_WARNING=20     #In percent
THRESHOLD_CRITICAL=10    #In percent
 
WARNING=0
CRITICAL=0
 
WARNING_ALERT=0
CRITICAL_ALERT=0
 
### Create a temporary file to compose an email
mail_content=`mktemp`
 
SILENT=:
 
### Read the command line parameters
while getopts ":w:c:d:" option; do
    case ${option} in
        w)
            THRESHOLD_WARNING=${OPTARG}
            ;;
        c)
            THRESHOLD_CRITICAL=${OPTARG}
            ;;
        d)
            set -f
            disks+=($OPTARG)
            ;;
    esac
done
 
send_notification(){
    $SILENT echo "Sending email notification to ${NOTIFICATION_EMAIL}"
    SUBJECT="${1} ALERT: Host $HOSTNAME Disk Check"
    mutt -s "${SUBJECT}" ${NOTIFICATION_EMAIL} < ${mail_content}
}
 
### Function to check available space on a given disk 
check_disk_space(){
 
    local total_used_space=`df -h $1 | awk '{print $5}' | tail -1`
    local used_space_percent=`echo ${total_used_space:0:-1}`
    local free_space_percent=$(( 100 - $used_space_percent ))
 
    if (( $free_space_percent <= ${THRESHOLD_CRITICAL} )); then
        CRITICAL=1
        return 2
    elif (( $free_space_percent <= ${THRESHOLD_WARNING} )); then
        WARNING=1
        return 1
    else
        OK=1
        return 0
    fi
}
 
### Check if the disk is passed as command line else select root (/)
if [ ${#disks[@]} -lt 1 ]; then
        echo "No disk is provided, Selecting root disk as default"
        disks[0]="/"
fi
 
### Create email content
echo "Attention:
 
One or more disks are low in space on host \"${HOSTNAME}\".
" >> ${mail_content}
 
 
$SILENT echo ":: CHECK CONDITION"
$SILENT echo "-- Warning if free disk is below: ${THRESHOLD_WARNING}%"
$SILENT echo "-- Critical if free disk is below: ${THRESHOLD_CRITICAL}%"
 
$SILENT echo ":: CHECKING DISKS"
$SILENT echo "-- Total disk to check: ${disks[@]}"
 
### Calling function check_disk_space for all disk one by one
for disk in "${disks[@]}"; do
    check_disk_space ${disk}
    if [ ${CRITICAL} -eq 1 ];then
        echo "  => Disk \"${disk}\" is in critical state" | tee -a  ${mail_content}
        CRITICAL_ALERT=1
        CRITICAL=0
    elif [ ${WARNING} -eq 1 ];then
        echo "  => Disk \"${disk}\" is in warning state" | tee -a ${mail_content}
        WARNING_ALERT=1
        WARNING=0
    else
        $SILENT echo "  => Disk \"${disk}\" is ok"
    fi
done
 
### Finish mail content
 
echo "
--
Thanks
$HOSTNAME" >>  ${mail_content}
 
## Notify if at least one disk is in warning or critical state
if [ ${CRITICAL_ALERT} -ne 0 ]; then
     [[ $ENABLE_EMAIL_ALERT -eq 1 ]] && send_notification CRITICAL	
elif [ ${WARNING_ALERT} -ne 0 ]; then
     [[ $ENABLE_EMAIL_ALERT -eq 1 ]] && send_notification WARNING
else
     $SILENT echo "All disk(s) are okay!"
fi
 
#####################      End of Script     ############################
