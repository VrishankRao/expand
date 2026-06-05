import { Camera, Link as LinkIcon, GripVertical, Trash2 } from 'lucide-react';
import { useState } from 'react';

type Theme = 'light' | 'dark' | 'green';

interface Link {
  id: string;
  label: string;
  url: string;
  enabled: boolean;
  category: string;
}

export default function App() {
  const [displayName, setDisplayName] = useState('');
  const [bio, setBio] = useState('');
  const [theme, setTheme] = useState<Theme>('light');
  const [publicVisibility, setPublicVisibility] = useState(true);
  const [email, setEmail] = useState('');
  const [links, setLinks] = useState<Link[]>([]);
  const [newLinkLabel, setNewLinkLabel] = useState('');
  const [newLinkUrl, setNewLinkUrl] = useState('');

  const addLink = () => {
    if (newLinkLabel.trim() && newLinkUrl.trim()) {
      const newLink: Link = {
        id: Date.now().toString(),
        label: newLinkLabel,
        url: newLinkUrl,
        enabled: true,
        category: 'OTHER',
      };
      setLinks([...links, newLink]);
      setNewLinkLabel('');
      setNewLinkUrl('');
    }
  };

  const toggleLink = (id: string) => {
    setLinks(links.map(link =>
      link.id === id ? { ...link, enabled: !link.enabled } : link
    ));
  };

  const deleteLink = (id: string) => {
    setLinks(links.filter(link => link.id !== id));
  };

  const themeStyles = {
    light: {
      bg: 'bg-gray-50',
      text: 'text-gray-900',
      cardBg: 'bg-white',
      border: 'border-gray-200',
      inputBg: 'bg-gray-50',
      inputBorder: 'border-gray-300',
      inputText: 'text-gray-900',
      labelText: 'text-gray-600',
      mutedText: 'text-gray-500',
      hoverBg: 'hover:bg-gray-100',
      buttonBg: 'bg-gray-100',
      buttonBorder: 'border-gray-300',
      buttonActive: 'bg-gray-900 text-white border-gray-900',
      primaryButton: 'bg-emerald-500 hover:bg-emerald-600 text-white',
    },
    dark: {
      bg: 'bg-[#0a1628]',
      text: 'text-white',
      cardBg: 'bg-[#0d1b2e]',
      border: 'border-gray-700',
      inputBg: 'bg-[#0a1628]',
      inputBorder: 'border-gray-700',
      inputText: 'text-white',
      labelText: 'text-gray-300',
      mutedText: 'text-gray-400',
      hoverBg: 'hover:bg-gray-800',
      buttonBg: 'bg-[#0a1628]',
      buttonBorder: 'border-gray-700',
      buttonActive: 'bg-gray-700 border-gray-600',
      primaryButton: 'bg-emerald-500 hover:bg-emerald-600 text-white',
    },
    green: {
      bg: 'bg-[#0d3b2e]',
      text: 'text-white',
      cardBg: 'bg-[#0f4d3c]',
      border: 'border-emerald-800',
      inputBg: 'bg-[#0d3b2e]',
      inputBorder: 'border-emerald-700',
      inputText: 'text-white',
      labelText: 'text-emerald-100',
      mutedText: 'text-emerald-200',
      hoverBg: 'hover:bg-emerald-900',
      buttonBg: 'bg-[#0d3b2e]',
      buttonBorder: 'border-emerald-700',
      buttonActive: 'bg-emerald-700 border-emerald-600',
      primaryButton: 'bg-emerald-500 hover:bg-emerald-600 text-white',
    },
  };

  const styles = themeStyles[theme];

  return (
    <div className={`h-screen flex flex-col ${styles.bg} ${styles.text} overflow-hidden`}>
      {/* Header */}
      <header className={`border-b ${styles.border} px-6 py-3 flex-shrink-0`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-xl font-bold">XPAND</div>
            <span className={`text-xs ${styles.mutedText}`}>v1.0.0</span>
          </div>
          <div className="flex items-center gap-4">
            <span className={`text-xs ${styles.labelText}`}>+17654339025</span>
            <button className={`px-4 py-1.5 text-xs border ${styles.border} rounded-lg ${styles.hoverBg} transition-colors`}>
              Log out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-auto">
        <div className="px-6 py-5">
          <div className="max-w-[1400px] mx-auto grid grid-cols-[400px_1fr] gap-5">
            {/* WhatsApp Profile Settings */}
            <div className={`border ${styles.border} rounded-xl p-5 ${styles.cardBg}`}>
              <h2 className="text-base font-semibold mb-1">WhatsApp Profile Settings</h2>
              <p className={`text-xs ${styles.mutedText} mb-4`}>Update: Saved locally</p>

              {/* Profile Picture */}
              <div className="flex items-center gap-4 mb-4">
                <div className={`w-14 h-14 rounded-full ${styles.inputBg} border-2 ${styles.inputBorder} flex items-center justify-center`}>
                  <Camera className={`w-6 h-6 ${styles.mutedText}`} />
                </div>
                <div>
                  <button className={`text-xs px-3 py-1.5 border ${styles.border} rounded-lg ${styles.hoverBg} transition-colors`}>
                    Upload Photo
                  </button>
                  <p className={`text-[10px] ${styles.mutedText} mt-1`}>JPG, PNG or GIF (max. 2MB)</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <label className={`block text-[10px] font-medium ${styles.labelText} mb-1.5 uppercase tracking-wide`}>
                    Display Name
                  </label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    className={`w-full ${styles.inputBg} border ${styles.inputBorder} rounded-lg px-3 py-2 text-sm ${styles.inputText} placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-transparent transition-all`}
                    placeholder="Ex: Jane Doe"
                  />
                </div>

                <div>
                  <label className={`block text-[10px] font-medium ${styles.labelText} mb-1.5 uppercase tracking-wide`}>
                    Bio
                  </label>
                  <input
                    type="text"
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                    className={`w-full ${styles.inputBg} border ${styles.inputBorder} rounded-lg px-3 py-2 text-sm ${styles.inputText} placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-transparent transition-all`}
                    placeholder="Tell us about yourself"
                  />
                </div>
              </div>

              <div className="mb-4">
                <label className={`block text-[10px] font-medium ${styles.labelText} mb-2 uppercase tracking-wide`}>
                  Theme
                </label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setTheme('light')}
                    className={`flex-1 py-2 text-sm rounded-lg border transition-all ${
                      theme === 'light'
                        ? styles.buttonActive
                        : `${styles.buttonBg} ${styles.buttonBorder} ${styles.hoverBg}`
                    }`}
                  >
                    Light
                  </button>
                  <button
                    onClick={() => setTheme('dark')}
                    className={`flex-1 py-2 text-sm rounded-lg border transition-all ${
                      theme === 'dark'
                        ? styles.buttonActive
                        : `${styles.buttonBg} ${styles.buttonBorder} ${styles.hoverBg}`
                    }`}
                  >
                    Dark
                  </button>
                  <button
                    onClick={() => setTheme('green')}
                    className={`flex-1 py-2 text-sm rounded-lg border transition-all ${
                      theme === 'green'
                        ? styles.buttonActive
                        : `${styles.buttonBg} ${styles.buttonBorder} ${styles.hoverBg}`
                    }`}
                  >
                    Green
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between mb-4 pb-4 border-b" style={{ borderColor: styles.border.includes('gray-200') ? '#e5e7eb' : styles.border.includes('gray-700') ? '#374151' : '#065f46' }}>
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide">Public Visibility</div>
                  <div className={`text-[10px] ${styles.mutedText} mt-0.5`}>Visible everywhere across links</div>
                </div>
                <button
                  onClick={() => setPublicVisibility(!publicVisibility)}
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    publicVisibility ? 'bg-emerald-500' : theme === 'light' ? 'bg-gray-300' : 'bg-gray-700'
                  }`}
                >
                  <div
                    className={`absolute top-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-md ${
                      publicVisibility ? 'left-6' : 'left-0.5'
                    }`}
                  />
                </button>
              </div>

              <button className={`w-full ${styles.primaryButton} py-2.5 text-sm rounded-lg font-medium transition-colors`}>
                Save Profile Changes
              </button>
            </div>

            {/* Right Column */}
            <div className="space-y-5">
              {/* Lead Notifications */}
              <div className={`border ${styles.border} rounded-xl p-5 ${styles.cardBg}`}>
                <h2 className="text-base font-semibold mb-1">Lead Notifications</h2>
                <p className={`text-xs ${styles.mutedText} mb-4`}>Get emails instantly when you capture leads.</p>

                <div className="flex gap-2">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@domain.com"
                    className={`flex-1 ${styles.inputBg} border ${styles.inputBorder} rounded-lg px-3 py-2 text-sm ${styles.inputText} placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-transparent transition-all`}
                  />
                  <button className={`px-4 py-2 text-xs border ${styles.border} rounded-lg ${styles.hoverBg} font-medium transition-colors whitespace-nowrap`}>
                    Verify Email
                  </button>
                </div>
              </div>

              {/* Links */}
              <div className={`border ${styles.border} rounded-xl p-5 ${styles.cardBg}`}>
                <div className="mb-4">
                  <h2 className="text-base font-semibold mb-0.5">WhatsApp CTAs</h2>
                  <p className={`text-xs ${styles.mutedText}`}>Add up to 10 active links. Pasted URLs auto-classify to set recommended CTAs.</p>
                </div>

                {/* Add Link Form */}
                <div className={`border ${styles.border} rounded-xl p-4 mb-4`}>
                  <div className="flex gap-3">
                    <input
                      type="text"
                      value={newLinkLabel}
                      onChange={(e) => setNewLinkLabel(e.target.value)}
                      placeholder="Button Label (e.g. Chat Support)"
                      className={`flex-1 ${styles.inputBg} border ${styles.inputBorder} rounded-lg px-3 py-2 text-sm ${styles.inputText} placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-transparent transition-all`}
                    />
                    <input
                      type="text"
                      value={newLinkUrl}
                      onChange={(e) => setNewLinkUrl(e.target.value)}
                      placeholder="WhatsApp Link (e.g. wa.me/...)"
                      className={`flex-1 ${styles.inputBg} border ${styles.inputBorder} rounded-lg px-3 py-2 text-sm ${styles.inputText} placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-transparent transition-all`}
                    />
                    <button
                      onClick={addLink}
                      className={`${styles.primaryButton} px-5 py-2 text-sm rounded-lg font-medium transition-colors whitespace-nowrap`}
                    >
                      Add
                    </button>
                  </div>
                </div>

                {/* Links List */}
                <div className="space-y-3">
                  {links.length === 0 ? (
                    <div className={`text-center py-6 ${styles.mutedText}`}>
                      <LinkIcon className="w-10 h-10 mx-auto mb-2 opacity-30" />
                      <p className="text-xs">No links added yet</p>
                    </div>
                  ) : (
                    links.map((link) => (
                      <div
                        key={link.id}
                        className={`border ${styles.border} rounded-xl p-4 flex items-center gap-4`}
                      >
                        <GripVertical className={`w-4 h-4 ${styles.mutedText} cursor-grab`} />
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-semibold mb-1">{link.label}</h3>
                          <div className="flex items-center gap-2">
                            <span className={`text-[10px] px-2 py-0.5 rounded ${
                              theme === 'light' ? 'bg-gray-200 text-gray-600' :
                              theme === 'dark' ? 'bg-gray-800 text-gray-300' :
                              'bg-emerald-900 text-emerald-200'
                            }`}>
                              {link.category}
                            </span>
                            <span className={`text-xs ${styles.mutedText} truncate`}>{link.url}</span>
                          </div>
                        </div>
                        <button
                          onClick={() => toggleLink(link.id)}
                          className={`relative w-12 h-6 rounded-full transition-colors flex-shrink-0 ${
                            link.enabled ? 'bg-emerald-500' : theme === 'light' ? 'bg-gray-300' : 'bg-gray-700'
                          }`}
                        >
                          <div
                            className={`absolute top-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-md ${
                              link.enabled ? 'left-6' : 'left-0.5'
                            }`}
                          />
                        </button>
                        <button
                          onClick={() => deleteLink(link.id)}
                          className={`${styles.mutedText} hover:text-red-500 transition-colors flex-shrink-0`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}