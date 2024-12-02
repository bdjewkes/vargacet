type SoundEffect = {
    id: string;
    url: string;
    volume?: number;
};

class SoundManager {
    private static instance: SoundManager;
    private audioCache: Map<string, HTMLAudioElement>;
    private enabled: boolean;

    private readonly SOUND_EFFECTS: SoundEffect[] = [
        { id: 'heal', url: '/sounds/heal.mp3', volume: 0.7 },
        { id: 'damage', url: '/sounds/damage.mp3', volume: 0.8 },
        { id: 'death', url: '/sounds/death.mp3', volume: 0.9 },
        { id: 'explosion', url: '/sounds/explosion.mp3', volume: 0.8 },
        { id: 'punch', url: '/sounds/punch.mp3', volume: 0.7 },
        { id: 'bow', url: '/sounds/bow.mp3', volume: 0.6 }
    ];

    private constructor() {
        this.audioCache = new Map();
        this.enabled = true;
        this.preloadSounds();
    }

    public static getInstance(): SoundManager {
        if (!SoundManager.instance) {
            SoundManager.instance = new SoundManager();
        }
        return SoundManager.instance;
    }

    private preloadSounds(): void {
        this.SOUND_EFFECTS.forEach(effect => {
            const audio = new Audio(effect.url);
            audio.volume = effect.volume || 1.0;
            this.audioCache.set(effect.id, audio);
        });
    }

    public playSound(id: string): void {
        if (!this.enabled) return;

        const audio = this.audioCache.get(id);
        if (audio) {
            // Create a new instance for overlapping sounds
            const newAudio = audio.cloneNode() as HTMLAudioElement;
            newAudio.volume = audio.volume;
            newAudio.play().catch(error => {
                console.warn(`Failed to play sound ${id}:`, error);
            });
        }
    }

    public playAbilitySound(abilityId: string): void {
        switch (abilityId) {
            case 'heal_1':
                this.playSound('heal');
                break;
            case 'damage_1':
                this.playSound('punch');
                break;
            case 'ranged_1':
                this.playSound('bow');
                break;
            case 'explosion_1':
                this.playSound('explosion');
                break;
            default:
                // Default combat sound for unknown abilities
                this.playSound('damage');
        }
    }

    public playDeathSound(): void {
        this.playSound('death');
    }

    public toggleSound(): void {
        this.enabled = !this.enabled;
    }

    public isEnabled(): boolean {
        return this.enabled;
    }
}

export default SoundManager;
