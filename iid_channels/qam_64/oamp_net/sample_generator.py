import torch
import numpy as np

class sample_generator(object):
	def __init__(self, batch_size, mod_n, NR):
		self.batch_size = batch_size
		self.Hdataset_powerdB = np.inf
		self.NR = NR
		self.mod_n = mod_n
		self.constellation, _ = self.QAM_N_const()
		self.real_QAM_const, self.imag_QAM_const = self.QAM_const()

	def QAM_const(self):
		sqrt_mod_n = np.int(np.sqrt(self.mod_n))
		real_qam_consts = torch.empty((self.mod_n), dtype=torch.int64)
		imag_qam_consts = torch.empty((self.mod_n), dtype=torch.int64)
		for i in range(sqrt_mod_n):
			for j in range(sqrt_mod_n):
				index = sqrt_mod_n*i + j
				real_qam_consts[index] = i
				imag_qam_consts[index] = j

		return(self.modulate(real_qam_consts), self.modulate(imag_qam_consts))

	def QAM_N_const(self):
		n = self.mod_n
		constellation = np.linspace(int(-np.sqrt(n)+1), int(np.sqrt(n)-1), int(np.sqrt(n)))
		alpha = np.sqrt((constellation ** 2).mean())
		constellation /= (alpha * np.sqrt(2))
		constellation = torch.tensor(constellation).to(dtype=torch.float32)
		return constellation, float(alpha)

	def QAM_N_ind(self, NT, batch_size):
		indices_QAM = torch.randint(low=0, high=(np.int(np.sqrt(self.mod_n))), size=(batch_size, 2*NT))
		return indices_QAM

	def random_indices(self, NT, batch_size):
		indices = self.QAM_N_ind(NT, batch_size)
		return indices

	def batch_matvec_mul(self, A, b):
		return torch.einsum(('ijk,ik->ij'), (A,b))
	
	def modulate(self, indices):
		x = self.constellation[indices]
		return x

	def demodulate(self, y):
		shape = y.shape
		y = torch.reshape(y, shape=(-1,1))
		constellation = torch.reshape(self.constellation, shape=(1, -1))
		difference = torch.abs(y - self.constellation)
		indices = torch.argmin(difference, dim=1)
		indices = torch.reshape(indices, shape=shape)
		return indices

	def joint_indices(self, indices):
		real_part, complex_part = torch.chunk(indices, 2, dim=1)
		joint_indices = np.int(np.sqrt(self.mod_n))*real_part + complex_part
		return joint_indices

	def channel(self, x, snr_db_min, snr_db_max, NT, batch_size):

		Hr = torch.empty((batch_size, self.NR, NT)).normal_(mean=0,std=1./np.sqrt(2.*self.NR))
		Hi = torch.empty((batch_size, self.NR, NT)).normal_(mean=0,std=1./np.sqrt(2.*self.NR))
		h1 = torch.cat((Hr, -1. * Hi), dim=2)
		h2 = torch.cat((Hi, Hr), dim=2)
		H = torch.cat((h1, h2), dim=1)
		self.Hdataset_powerdB = 0.

		# Channel Noise
		snr_db = torch.empty((batch_size, 1)).uniform_(snr_db_min, snr_db_max)

		wr = torch.empty((batch_size, self.NR)).normal_(mean=0.0, std=1./np.sqrt(2.))
		wi = torch.empty((batch_size, self.NR)).normal_(mean=0.0, std=1./np.sqrt(2.))
		w = torch.cat((wr, wi), dim=1)

		# SNR
		H_powerdB = 10. * torch.log(torch.mean(torch.sum(H.pow(2), dim=1), dim=0)) / np.log(10.)
		average_H_powerdB = torch.mean(H_powerdB)
		average_x_powerdB = 10. * torch.log(torch.mean(torch.sum(x.pow(2), dim=1))) / np.log(10.)
 
		w *= torch.pow(10., (10.*np.log10(NT) + self.Hdataset_powerdB - snr_db - 10.*np.log10(self.NR))/20.)
		complexnoise_sigma = torch.pow(10., (10.*np.log10(NT) + self.Hdataset_powerdB - snr_db - 10.*np.log10(self.NR))/20.)

		# Channel Output
		y = self.batch_matvec_mul(H, x) + w
		sig_powdB = 10. * torch.log(torch.mean(torch.sum(torch.pow(self.batch_matvec_mul(H,x),2), dim=1))) / np.log(10.)
		noise_powdB = 10. * torch.log(torch.mean(torch.sum(torch.pow(w,2), axis=1))) / np.log(10.)
		actual_snrdB = sig_powdB - noise_powdB

		return y, H, complexnoise_sigma, actual_snrdB

	def give_batch_data(self, NT, snr_db_min=2, snr_db_max=7, batch_size=None):
		if (batch_size==None):
			batch_size = self.batch_size
		indices = self.random_indices(NT, batch_size)
		joint_indices = self.joint_indices(indices)
		x = self.modulate(indices)
		y, H, complexnoise_sigma, _ = self.channel(x, snr_db_min, snr_db_max, NT, batch_size)
		return H, y, x, joint_indices, complexnoise_sigma.squeeze()