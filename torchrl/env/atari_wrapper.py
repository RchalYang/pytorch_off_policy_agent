import gym
import numpy as np
import cv2
from collections import deque

from .base_wrapper import BaseWrapper

"""
Basically from OpenAI Baseline
"""

class NoopResetEnv( BaseWrapper):
    def __init__(self, env, noop_max=30):
        """Sample initial states by taking random number of no-ops on reset.
        No-op is assumed to be action 0.
        """
        super().__init__(env)
        self.noop_max = noop_max
        self.override_num_noops = None
        self.noop_action = 0
        assert env.unwrapped.get_action_meanings()[0] == 'NOOP'

    def reset(self, **kwargs):
        """ Do no-op action for a number of steps in [1, noop_max]."""
        self.env.reset(**kwargs)
        if self.override_num_noops is not None:
            noops = self.override_num_noops
        else:
            noops = self.unwrapped.np_random.randint(1, self.noop_max + 1) #pylint: disable=E1101
        assert noops > 0
        obs = None
        for _ in range(noops):
            obs, _, done, _ = self.env.step(self.noop_action)
            if done:
                obs = self.env.reset(**kwargs)
        return obs

    def step(self, ac):
        """
        Run a single step.

        Args:
            self: (todo): write your description
            ac: (array): write your description
        """
        return self.env.step(ac)

class FireResetEnv( BaseWrapper ):
    def __init__(self, env):
        """Take action on reset for environments that are fixed until firing."""
        super().__init__(env)
        assert env.unwrapped.get_action_meanings()[1] == 'FIRE'
        assert len(env.unwrapped.get_action_meanings()) >= 3

    def reset(self, **kwargs):
        """
        Reset the environment.

        Args:
            self: (todo): write your description
        """
        self.env.reset(**kwargs)
        obs, _, done, _ = self.env.step(1)
        if done:
            self.env.reset(**kwargs)
        obs, _, done, _ = self.env.step(2)
        if done:
            self.env.reset(**kwargs)
        return obs

    def step(self, ac):
        """
        Run a single step.

        Args:
            self: (todo): write your description
            ac: (array): write your description
        """
        return self.env.step(ac)

class EpisodicLifeEnv( BaseWrapper):
    def __init__(self, env):
        """Make end-of-life == end-of-episode, but only reset on true game over.
        Done by DeepMind for the DQN and co. since it helps value estimation.
        """
        super().__init__( env )
        self.lives = 0
        self.was_real_done  = True

    def step(self, action):
        """
        Perform action.

        Args:
            self: (todo): write your description
            action: (int): write your description
        """
        obs, reward, done, info = self.env.step(action)
        self.was_real_done = done
        # check current lives, make loss of life terminal,
        # then update lives to handle bonus lives
        lives = self.env.unwrapped.ale.lives()
        if lives < self.lives and lives > 0:
            # for Qbert sometimes we stay in lives == 0 condition for a few frames
            # so it's important to keep lives > 0, so that we only reset once
            # the environment advertises done.
            done = True
        self.lives = lives
        return obs, reward, done, info

    def reset(self, **kwargs):
        """Reset only when lives are exhausted.
        This way all states are still reachable even though lives are episodic,
        and the learner need not know about any of this behind-the-scenes.
        """
        if self.was_real_done:
            obs = self.env.reset(**kwargs)
        else:
            # no-op step to advance from terminal/lost life state
            obs, _, _, _ = self.env.step(0)
        self.lives = self.env.unwrapped.ale.lives()
        return obs

class MaxAndSkipEnv( BaseWrapper):
    def __init__(self, env, skip=4):
        """Return only every `skip`-th frame"""
        super().__init__( env)
        # most recent raw observations (for max pooling across time steps)
        self._obs_buffer = np.zeros((2,)+env.observation_space.shape, dtype=np.uint8)
        self._skip       = skip

    def step(self, action):
        """Repeat action, sum reward, and max over last observations."""
        total_reward = 0.0
        done = None
        for i in range(self._skip):
            obs, reward, done, info = self.env.step(action)
            if i == self._skip - 2: self._obs_buffer[0] = obs
            if i == self._skip - 1: self._obs_buffer[1] = obs
            total_reward += reward
            if done:
                break
        # Note that the observation on the done=True frame
        # doesn't matter
        max_frame = self._obs_buffer.max(axis=0)

        return max_frame, total_reward, done, info

    def reset(self, **kwargs):
        """
        Reset the environment.

        Args:
            self: (todo): write your description
        """
        return self.env.reset(**kwargs)

class ClipRewardEnv( gym.RewardWrapper, BaseWrapper ):
    def __init__(self, env):
        """
        Initialize the environment.

        Args:
            self: (todo): write your description
            env: (todo): write your description
        """
        super().__init__(env)

    def reward(self, reward):
        """Bin reward to {+1, 0, -1} by its sign."""
        return np.sign(reward)

class LazyFrames(object):
    def __init__(self, frames):
        """This object ensures that common frames between the observations are only stored once.
        It exists purely to optimize memory usage which can be huge for DQN's 1M frames replay
        buffers.
        This object should only be converted to numpy array before being passed to the model.
        You'd not believe how complex the previous solution was."""
        self._frames = frames
        self._out = None

    def _force(self):
        """
        Concatenames.

        Args:
            self: (todo): write your description
        """
        if self._out is None:
            self._out = np.concatenate(self._frames, axis=0)
            self._frames = None
        return self._out

    def __array__(self, dtype=None):
        """
        Return a copy of this array.

        Args:
            self: (todo): write your description
            dtype: (todo): write your description
        """
        out = self._force()
        if dtype is not None:
            out = out.astype(dtype)
        return out

    def __len__(self):
        """
        Returns the number of bytes.

        Args:
            self: (todo): write your description
        """
        return len(self._force())

    def __getitem__(self, i):
        """
        Returns the item at the given index.

        Args:
            self: (todo): write your description
            i: (todo): write your description
        """
        return self._force()[i]
   
class WarpFrame(gym.ObservationWrapper, BaseWrapper):
    """Warp frames to 84x84 as done in the Nature paper and later work."""
    def __init__(self, env, width=84, height=84, grayscale=True):
        """
        Initialize the array.

        Args:
            self: (todo): write your description
            env: (todo): write your description
            width: (int): write your description
            height: (int): write your description
            grayscale: (bool): write your description
        """
        super().__init__(env)
        self.width = width
        self.height = height
        self.grayscale = grayscale
        if self.grayscale:
            self.observation_space = gym.spaces.Box(low=0, high=255,
                shape=(1, self.height, self.width), dtype=np.uint8)
        else:
            self.observation_space = gym.spaces.Box(low=0, high=255,
                shape=(3, self.height, self.width), dtype=np.uint8)

    def observation(self, frame):
        """
        Convert an observation to the image.

        Args:
            self: (todo): write your description
            frame: (todo): write your description
        """
        if self.grayscale:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
        if self.grayscale:
            frame = np.expand_dims(frame, -1)
        frame = np.transpose(frame, (2,0,1) )
        return frame

class FrameStack( BaseWrapper):
    def __init__(self, env, k):
        """Stack k last frames.
        Returns lazy array, which is much more memory efficient.
        See Also
        --------
        baselines.common.atari_wrappers.LazyFrames
        """
        super().__init__(env)
        self.k = k
        self.frames = deque([], maxlen=k)
        shp = env.observation_space.shape
        self.observation_space = gym.spaces.Box(low=0, high=255, shape=( (shp[0] * k,) + shp[1:] ), dtype=env.observation_space.dtype)

    def reset(self):
        """
        Reset the environment.

        Args:
            self: (todo): write your description
        """
        ob = self.env.reset()
        for _ in range(self.k):
            self.frames.append(ob)
        return self._get_ob()

    def step(self, action):
        """
        Run an environment todo.

        Args:
            self: (todo): write your description
            action: (int): write your description
        """
        ob, reward, done, info = self.env.step(action)
        self.frames.append(ob)
        return self._get_ob(), reward, done, info

    def _get_ob(self):
        """
        Return a list of the frame.

        Args:
            self: (todo): write your description
        """
        assert len(self.frames) == self.k
        return LazyFrames(list(self.frames))

class ScaledFloatFrame(gym.ObservationWrapper, BaseWrapper):
    def __init__(self, env):
        """
        Initialize an observation.

        Args:
            self: (todo): write your description
            env: (todo): write your description
        """
        super().__init__(env)
        self.observation_space = gym.spaces.Box(low=-0.5, high=0.5, shape=env.observation_space.shape, dtype=np.float32)

    def observation(self, observation):
        """
        Calculate the observation

        Args:
            self: (todo): write your description
            observation: (str): write your description
        """
        # careful! This undoes the memory optimization, use
        # with smaller replay buffers only.
        return np.array(observation).astype(np.float32) / 255.0 - 0.5
