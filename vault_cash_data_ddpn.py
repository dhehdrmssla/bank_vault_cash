# -*- coding: utf-8 -*-
"""vault_cash_data_DDPN.ipynb의 사본

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1JdcMHcRWUDkISTzTuLNJjQP_DiJWkPet
"""

import argparse
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import gymnasium as gym
from torch.distributions import Normal
from collections import namedtuple
import matplotlib.pyplot as plt
import easydict
import pandas as pd
import datetime
import random
from sklearn.preprocessing import StandardScaler

class bank_vault_cash(gym.Env):
    # 마감 이후 기준으로
    # state는 [월, 일, 시재, 한도]
    # action은 원화현수송
    metadata = {"render_modes": ["human"]}

    def __init__(self):

      total_data = pd.read_csv('/content/drive/MyDrive/total_data.csv')
      self.train_data = total_data[total_data['date'] <= '2022-12-31']
      self.test_data = total_data[total_data['date'] >= '2023-01-01']

    # reset은 state와 info를 return
    def reset(self):
      rand_idx = random.choice((self.train_data[self.train_data['day'] == 1]).index)
      year, month = self.train_data.iloc[rand_idx]['year'], self.train_data.iloc[rand_idx]['month']
      self.vault_cash_data = self.train_data[(self.train_data['year'] == year)&(self.train_data['month'] == month)].reset_index(drop=True).copy()
      self.episode_len = len(self.vault_cash_data)
      self.i = 0
      self.terminated = False
      self.truncated = False

      data = self.vault_cash_data.iloc[self.i]
      month = data['month']
      day = data['day']
      close_balance = data['close_balance']
      limit = data['limit']

      s = np.array([close_balance, limit])
      info = {}

      return s, info, self.episode_len

    # step은 s', r, terminated, truncated, info를 return
    def step(self, action):

      yesterday_data = self.vault_cash_data.iloc[self.i]

      self.i += 1
      self.vault_cash_data.loc[self.i, 'open_balance'] = yesterday_data['close_balance']
      self.vault_cash_data.loc[self.i, 'transportation_action'] = action
      self.vault_cash_data.iloc[self.i]
      self.vault_cash_data.loc[self.i, 'close_balance'] = self.vault_cash_data.iloc[self.i]['open_balance'] + self.vault_cash_data.iloc[self.i]['today_inout'] + self.vault_cash_data.iloc[self.i]['transportation_action']

      today_data = self.vault_cash_data.iloc[self.i]

      month = today_data['month']
      day = today_data['day']
      close_balance = today_data['close_balance']
      limit = today_data['limit']

      s_prime = np.array([close_balance, limit])

      #시재금 마이너스
      if yesterday_data['close_balance'] < 0:
        self.truncated = True
      else:
        self.truncated = False

      #수수료
      if action != 0:
        r_1 = -75000/1000000
      else:
        r_1 = 0
      # 월말평잔 한도 비교
      if self.i == (self.episode_len - 1):
        self.terminated = True
        end_month_balance_mean = self.vault_cash_data['close_balance'].mean()
        diff = end_month_balance_mean - today_data['limit']
        if diff > 0:
          r_2 = -(diff*1.2)/1000000 #내부금리
        else:
          r_2 = 0
      else:
        r_2 = 0

      return s_prime, r_1 + r_2, self.terminated, self.truncated, {}

    def test_reset(self):
      self.vault_cash_data = self.test_data.copy()
      self.episode_len = len(self.vault_cash_data)
      self.i = 0
      self.terminated = False
      self.truncated = False

      data = self.vault_cash_data.iloc[self.i]
      month = data['month']
      day = data['day']
      close_balance = data['close_balance']
      limit = data['limit']

      s = np.array([close_balance, limit])
      info = {}

      return s, info, self.episode_len

    # step은 s', r, terminated, truncated, info를 return
    def test_step(self, action):

      yesterday_data = self.vault_cash_data.iloc[self.i]

      self.i += 1
      self.vault_cash_data.loc[self.i, 'open_balance'] = yesterday_data['close_balance']
      self.vault_cash_data.loc[self.i, 'transportation_action'] = action
      self.vault_cash_data.iloc[self.i]
      self.vault_cash_data.loc[self.i, 'close_balance'] = self.vault_cash_data.iloc[self.i]['open_balance'] + self.vault_cash_data.iloc[self.i]['today_inout'] + self.vault_cash_data.iloc[self.i]['transportation_action']

      today_data = self.vault_cash_data.iloc[self.i]

      month = today_data['month']
      day = today_data['day']
      close_balance = today_data['close_balance']
      limit = today_data['limit']

      s_prime = np.array([close_balance, limit])

      #시재금 마이너스
      if yesterday_data['close_balance'] < 0:
        self.truncated = True
      else:
        self.truncated = False

      #수수료
      if action != 0:
        r_1 = -75000/1000000
      else:
        r_1 = 0
      # 월말평잔 한도 비교
      if self.i == (self.episode_len - 1):
        self.terminated = True
        end_month_balance_mean = self.vault_cash_data['close_balance'].mean()
        diff = end_month_balance_mean - today_data['limit']
        if diff > 0:
          r_2 = -(diff*1.2)/1000000 #내부금리
        else:
          r_2 = 0
      else:
        r_2 = 0

      return s_prime, r_1 + r_2, self.terminated, self.truncated, {}



device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

class ActorNet(nn.Module):
    def __init__(self):
        super(ActorNet, self).__init__()
        self.fc = nn.Linear(2, 100)
        self.mu_head = nn.Linear(100, 1)

    def forward(self, s):
        x = F.relu(self.fc(s))
        u = 14.0 * F.tanh(self.mu_head(x))
        u = 10. * F.tanh(self.mu_head(x))
        return u

class CriticNet(nn.Module):
    def __init__(self):
        super(CriticNet, self).__init__()
        self.fc = nn.Linear(3, 100)
        self.v_head = nn.Linear(100, 1)

    def forward(self, s, a):
        x = F.relu(self.fc(torch.cat([s, a], dim=1)))
        state_value = self.v_head(x)
        return state_value

class Memory():
    data_pointer = 0
    isfull = False

    def __init__(self, capacity):
        self.memory = np.empty(capacity, dtype=object)
        self.capacity = capacity

    def update(self, transition):
        self.memory[self.data_pointer] = transition
        self.data_pointer += 1
        if self.data_pointer == self.capacity:
            self.data_pointer = 0
            self.isfull = True

    def sample(self, batch_size):
        return np.random.choice(self.memory, batch_size)

class Agent:
    max_grad_norm = 0.5

    def __init__(self):
        self.training_step = 0
        self.var = 1.
        self.eval_cnet, self.target_cnet = CriticNet().float().to(device), CriticNet().float().to(device)
        self.eval_anet, self.target_anet = ActorNet().float().to(device), ActorNet().float().to(device)
        self.memory = Memory(2000)
        self.optimizer_c = optim.Adam(self.eval_cnet.parameters(), lr=1e-3)
        self.optimizer_a = optim.Adam(self.eval_anet.parameters(), lr=3e-4)

    def select_action(self, state):
        state = torch.from_numpy(state).float().unsqueeze(0).to(device)
        mu = self.eval_anet(state)
        dist = Normal(mu, torch.tensor(self.var, dtype=torch.float).to(device))
        action = dist.sample()
        #action.clamp(-2.0, 2.0)   #최대최소 적용
        return action.item()

    def save_param(self):
        torch.save(self.eval_anet.state_dict(), 'ddpg_anet_params.pkl')
        torch.save(self.eval_cnet.state_dict(), 'ddpg_cnet_params.pkl')

    def store_transition(self, transition):
        self.memory.update(transition)

    def update(self):
        self.training_step += 1

        transitions = self.memory.sample(32)
        s = torch.tensor([t.s for t in transitions], dtype=torch.float).to(device)
        a = torch.tensor([t.a for t in transitions], dtype=torch.float).view(-1, 1).to(device)
        r = torch.tensor([t.r for t in transitions], dtype=torch.float).view(-1, 1).to(device)
        s_ = torch.tensor([t.s_ for t in transitions], dtype=torch.float).to(device)

        with torch.no_grad():
            q_target = r + args.gamma * self.target_cnet(s_, self.target_anet(s_))
        q_eval = self.eval_cnet(s, a)

        # update critic net
        self.optimizer_c.zero_grad()
        c_loss = F.smooth_l1_loss(q_eval, q_target)
        c_loss.backward()
        nn.utils.clip_grad_norm_(self.eval_cnet.parameters(), self.max_grad_norm)
        self.optimizer_c.step()

        # update actor net
        self.optimizer_a.zero_grad()
        a_loss = -self.eval_cnet(s, self.eval_anet(s)).mean()
        a_loss.backward()
        nn.utils.clip_grad_norm_(self.eval_anet.parameters(), self.max_grad_norm)
        self.optimizer_a.step()

        if self.training_step % 200 == 0:
            self.target_cnet.load_state_dict(self.eval_cnet.state_dict())
        if self.training_step % 201 == 0:
            self.target_anet.load_state_dict(self.eval_anet.state_dict())

        self.var = max(self.var * 0.999, 0.01)

        return q_eval.mean().item()

def main(args):
    env = bank_vault_cash()
    #env.seed(args.seed)

    agent = Agent()
    TrainingRecord = namedtuple('TrainingRecord', ['ep', 'reward'])
    Transition = namedtuple('Transition', ['s', 'a', 'r', 's_'])

    training_records = []
    running_reward, running_q = -1000, 0

    for i_ep in range(1000):
        score = 0
        state, _, episode_len = env.reset()
        done = False

        for i in range(episode_len):

            action = agent.select_action(state)
            state_, reward, terminated, truncated, _ = env.step(action)
            done = (terminated or truncated)
            score += reward
            agent.store_transition(Transition(state, action, (reward + 8) / 8, state_))
            state = state_

            if agent.memory.isfull:
                q = agent.update()
                running_q = 0.99 * running_q + 0.01 * q

            if done :
              break

        running_reward = running_reward * 0.9 + score * 0.1
        training_records.append(TrainingRecord(i_ep, running_reward))

        if i_ep % args.log_interval == 0:
            print('Step {}\tAverage score: {:.2f}\tAverage Q: {:.2f}'.format(
                i_ep, running_reward, running_q))
            print(state, action)

    env.close()

    plt.plot([r.ep for r in training_records], [r.reward for r in training_records])
    plt.title('DDPG')
    plt.xlabel('Episode')
    plt.ylabel('Moving averaged episode reward')
    plt.savefig("ddpg.png")

    return env

if __name__ == '__main__':
#    parser = argparse.ArgumentParser(description='Solve the Pendulum-v0 with DDPG')
#    parser.add_argument('--gamma', type=float, default=0.9, metavar='G', help='discount factor (default: 0.9)')
#    parser.add_argument('--seed', type=int, default=0, metavar='N', help='random seed (default: 0)')
#    parser.add_argument('--render', action='store_true', help='render the environment')
#    parser.add_argument('--log-interval', type=int, default=10, metavar='N', help='interval between training status logs (default: 10)')
#    args = parser.parse_args()


    args = easydict.EasyDict({"gamma": 0.9, "seed": 0, 'render':'store_true', 'log_interval':10})

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)


    env = main(args)