'''
This is the base class of cumulator.
'''
import json
import time as t
import geocoder
import random
import pandas as pd
from geopy.geocoders import Nominatim
import GPUtil
import cpuinfo

country_dataset_path = 'country_dataset_adjusted.csv'
gpu_dataset_path = 'hardware/gpu.csv'
metrics_dataset_path = 'metrics/CO2_metrics.json'
metrics_dataset_path = 'metrics\CO2_metrics.json'


class Cumulator:

        #default value of TDP
        self.TDP=250
        # conversion to carbon footprint: average carbon intensity value in gCO2eq/kWh in the EU in 2014
        default_Carbon_Intensity = 447
        self.set_hardware(hardware)
        self.t0 = 0
        self.t1 = 0
        # times are in seconds
        self.time_list = []
        self.cumulated_time = 0
        # file sizes are in bytes
        self.file_size_list = []
        self.cumulated_data_traffic = 0
        # number of GPU
        self.n_gpu = 1
        # assumptions to approximate the carbon footprint
        # computation costs: consumption of a typical GPU in Watts converted to kWh/s
        self.hardware_load = self.TDP / 3.6e6
        # communication costs: average energy impact of traffic in a typical data centers, kWh/kB
        self.one_byte_model = 6.894E-8

    # starts accumulating time
    def on(self):
        self.t0 = t.time()
    
    def set_hardware(self, hardware):
        if hardware=="gpu":
            #search_gpu will try to detect the gpu on the device and set the corresponding TDP value as TDP value of Cumulator
            self.detect_gpu()
        elif hardware=="cpu":
            #search_cpu will try to detect the cpu on the device and set the corresponding TDP value as TDP value of Cumulator
            self.detect_cpu()
        #in case of wrong value of hardware let default TDP
        else:
            print(f'hardware expected to be "cpu" or "gpu". TDP set to default value {self.TDP}')
    
    #function for trying to detect gpu and set corresponding TDP value as TDP value of cumulator
    def detect_gpu(self):
        try:
            gpus = GPUtil.getGPUs()
            gpu_name=gpus[0].name
            df=pd.read_csv(gpu_dataset_path)
            #it uses contains for more flexibility
            row=df[df['name'].str.contains(gpu_name)]
            if row.empty:
                #if gpu not found then leave standard TDP value
                print(f'GPU not found. Standard TDP={self.TDP} assigned.')
            else:
                #otherwise assign gpu's TDP
                self.TDP=row.TDP.values[0]
        #ValueError arise when GPUtil can't communicate with the GPU driver 
        except (ValueError, IndexError):
            #in case no GPU can be found
            print(f'GPU not found. Standard TDP={self.TDP} assigned.')

    def detect_cpu(self):
        try:
            cpu_name=cpuinfo.get_cpu_info()['brand_raw']
            df=pd.read_csv(cpu_dataset_path)
            #it uses contains for more flexibility
            row=df[df['name'].str.contains(cpu_name)]
            if row.empty:
                #if gpu not found then leave standard TDP value
                print(f'CPU not found. Standard TDP={self.TDP} assigned.')
            else:
                #otherwise assign CPU's TDP
                self.TDP=row.TDP.values[0]
        except:
            #in case no CPU can be found
            print(f'[except] GPU not found. Standard TDP={self.TDP} assigned.')

    # stops accumulating time and records the value
    def off(self):
        self.t1 = t.time()
        self.cumulated_time += self.t1 - self.t0
        self.time_list.append(self.t1 - self.t0)

    def run(self, function, *args, **kwargs):
        """
        Measure the carbon footprint of `function`.

        Example
        --------
        >>> # imports
        >>> from sklearn.linear_model import LinearRegression
        >>> from sklearn import datasets
        >>> # initialization
        >>> cumulator = Cumulator()
        >>> model = LinearRegression()
        >>> diabetes_X, diabetes_y = datasets.load_diabetes(return_X_y=True)
        >>> # without output and with keywords arguments
        >>> cumulator.run(model.fit, X=diabetes_X, y=diabetes_y)
        >>> # with output and without keywords arguments
        >>> y = cumulator.run(model.predict, diabetes_X)
        >>> # show results
        >>> cumulator.display_carbon_footprint()


        :param function: function to measure.
        :param args: positional arguments of `function`.
        :param kwargs: keywords arguments of `function`.
        :return: output of `function`.
        """
        self.on()
        output = function(*args, **kwargs)
        self.off()
        return output

    def position_carbon_intensity(self):
        geolocator = Nominatim(user_agent="cumulator")
        g = geocoder.ip('me')
        df_data = pd.read_csv(country_dataset_path)

        location = geolocator.reverse(g.latlng)
        address = location.raw['address']
        code = address.get('country_code').upper()
        df_row = df_data[df_data['country'] == code]
        self.carbon_intensity = float(
            df_row['co2_per_unit_energy'] * 1000 if not df_row.empty else None)
        if self.carbon_intensity is None:
            raise AttributeError

    # records the amount of data transferred, file_size in kilo bytes
    def data_transferred(self, file_size):
        self.file_size_list.append(file_size)
        self.cumulated_data_traffic += file_size

    # computes time based carbon footprint due to computations
    def computation_costs(self):
        return self.cumulated_time * self.n_gpu * self.hardware_load * self.carbon_intensity

    # computes the carbon footprint due to communication
    def communication_costs(self):
        return self.one_byte_model * self.cumulated_data_traffic * self.carbon_intensity

    # computes the total carbon footprint
    def total_carbon_footprint(self):
        return self.computation_costs() + self.communication_costs()

    # prints the carbon footprint in the terminal
    def display_carbon_footprint(self):
        print('########\nOverall carbon footprint: %s gCO2eq\n########' %
              "{:.2e}".format(self.total_carbon_footprint()))
        print('Carbon footprint due to computations: %s gCO2eq' %
              "{:.2e}".format(self.computation_costs()))
        print('Carbon footprint due to communications: %s gCO2eq' %
              "{:.2e}".format(self.communication_costs()))
        # loading metrics dataset
        with open(metrics_dataset_path) as file:
            metrics = json.load(file)
            # computing equivalent of gCO2eq
            for metric in metrics:
                metric['equivalent'] = float(metric['eq_factor']) * (self.total_carbon_footprint())
            # select random equivalent metrics and print
            metric = metrics[random.randint(0, len(metrics) - 1)]
            print('This carbon footprint is equivalent to {:0.2e} {}.'.format(metric['equivalent'],
                                                                              metric['measure'].lower()))
