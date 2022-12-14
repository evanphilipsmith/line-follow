import time

import cv2
import depthai as dai

import toolbox

THROTTLE = 0.15


class VESC:
    ''' 
    VESC Motor controler using pyvesc
    This is used for most electric scateboards.
    
    inputs: serial_port---- port used communicate with vesc. for linux should be something like /dev/ttyACM1
    has_sensor=False------- default value from pyvesc
    start_heartbeat=True----default value from pyvesc (I believe this sets up a heartbeat and kills speed if lost)
    baudrate=115200--------- baudrate used for communication with VESC
    timeout=0.05-------------time it will try before giving up on establishing connection
    
    percent=.2--------------max percentage of the dutycycle that the motor will be set to
    outputs: none
    
    uses the pyvesc library to open communication with the VESC and sets the servo to the angle (0-1) and the duty_cycle(speed of the car) to the throttle (mapped so that percentage will be max/min speed)
    
    Note that this depends on pyvesc, but using pip install pyvesc will create a pyvesc file that
    can only set the speed, but not set the servo angle. 
    
    Instead please use:
    pip install git+https://github.com/LiamBindle/PyVESC.git@master
    to install the pyvesc library
    '''
    def __init__(
            self,
            serial_port: str,
            percent: float = 0.2,
            has_sensor: bool = False,
            start_heartbeat: bool = True,
            baudrate: int = 115200,
            timeout: float = 0.05,
            steering_scale: float = 1.0,
            steering_offset: float = 0.0):
        try:
            import pyvesc
        except Exception as err:
            print("\n\n\n\n", err, "\n")
            print("please use the following command to import pyvesc so that you can also set")
            print("the servo position:")
            print("pip install git+https://github.com/LiamBindle/PyVESC.git@master")
            print("\n\n\n")
            time.sleep(1)
            raise

        assert percent <= 1 and percent >= -1,'\n\nOnly percentages are allowed for MAX_VESC_SPEED (we recommend a value of about .2) (negative values flip direction of motor)'
        self.steering_scale = steering_scale
        self.steering_offset = steering_offset
        self.percent = percent
        
        try:
            self.v = pyvesc.VESC(serial_port, has_sensor, start_heartbeat, baudrate, timeout)
        except Exception as err:
            print("\n\n\n\n", err)
            print("\n\nto fix permission denied errors, try running the following command:")
            print("sudo chmod a+rw {}".format(serial_port), "\n\n\n\n")
            time.sleep(1)
            raise

    def run(self, angle, throttle):
        self.v.set_servo((angle * self.steering_scale) + self.steering_offset)
        self.v.set_duty_cycle(throttle*self.percent)


if __name__ == "__main__":
    vesc = VESC('/dev/ttyACM0', steering_offset=0.5)

    pipeline = dai.Pipeline()
    camRgb = pipeline.create(dai.node.ColorCamera)
    xoutRgb = pipeline.create(dai.node.XLinkOut)
    xoutRgb.setStreamName("rgb")
    camRgb.setPreviewSize(960, 540)
    camRgb.setInterleaved(False)
    camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB)
    camRgb.preview.link(xoutRgb.input)

    with dai.Device(pipeline, usb2Mode=True) as device:
        print('Connected cameras: ', device.getConnectedCameras())
        print('USB speed: ', device.getUsbSpeed().name)
        if device.getBootloaderVersion() is not None:
            print('Bootloader version: ', device.getBootloaderVersion())

        qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        while True:
            inRgb = qRgb.get()  # blocking call, will wait until a new data has arrived
            frame = inRgb.getCvFrame()  # Retrieve 'bgr' (opencv format) frame

            overlay, steering_line = toolbox.run_yellow_segmentation_pipeline(frame)
            if steering_line is None:
                overlay, steering_line = toolbox.run_lane_detection_pipeline(frame)

            steering_cmd = toolbox.steering_command(steering_line, frame.shape[1])
            print(steering_cmd)
            vesc.run(steering_cmd, THROTTLE)  # TODO does killing the script turn off the vesc or do we need to send a shutdown signal?

            output = cv2.addWeighted(frame, 0.8, overlay, 1, 1)
            output_small = cv2.resize(output, (480, 270), interpolation=cv2.INTER_LINEAR)
            cv2.imshow("frame", output_small)
            if cv2.waitKey(1) == ord('q'):
                break
        cv2.destroyAllWindows()
