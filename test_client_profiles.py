import copy
import json
from pathlib import Path
import struct
import unittest

import client_profiles
import model_audit

ROOT = Path(__file__).resolve().parent


class ClientProfileTests(unittest.TestCase):
    def test_grimfall_decoder_observed_header(self):
        # First 80 bytes from the installed Grimfall HumanFemale model.
        encoded = bytes.fromhex('4f4432302129576daa57c413f0219f142c5841f7eeef839c9077d0f767ac7b00912fb53090be02728f8334c7a2e78b55ea96b96a4c90f82546e021975277ac72212b61eca55a427748e115833d5ea0c6')
        decoded = client_profiles.decode_grimfall(encoded)
        self.assertEqual(decoded[:8], b'MD20' + struct.pack('<I', 264))
        self.assertEqual(struct.unpack_from('<4I', decoded, 44), (252, 7934192, 27, 7958464))
        self.assertEqual(client_profiles.grimfall_key(encoded), 0x1af6cedb)
        self.assertEqual(client_profiles.decode_grimfall(decoded), decoded)
        for data in (b'', b'OD20', b'XX20' + b'\0'*20):
            with self.assertRaises(ValueError):
                client_profiles.decode_grimfall(data)

    def test_missing_pelvis_key_resolved_from_thigh_topology(self):
        model = copy.deepcopy(json.loads((ROOT/'stock_profiles.json').read_text())['models']['HumanFemale'])
        expected = model['rig']['hips']
        model['key_bones'][5] = -1
        self.assertEqual(model_audit.select_rig(model)['hips'], expected)

    def test_unweighted_coincident_landmark_duplicate_and_ambiguity(self):
        model = copy.deepcopy(json.loads((ROOT/'stock_profiles.json').read_text())['models']['HumanFemale'])
        hand = model['rig']['hands'][0]
        duplicate = copy.deepcopy(model['bones'][hand])
        duplicate.update(index=len(model['bones']), parent=hand, weighted_vertices=0)
        model['bones'].append(duplicate)
        self.assertEqual(model_audit.select_rig(model)['hands'][0], hand)
        duplicate['weighted_vertices'] = 1
        with self.assertRaisesRegex(ValueError, 'Expected one bone'):
            model_audit.select_rig(model)

    def test_generated_client_headers_match_evidence(self):
        rigs = json.loads((ROOT/'client_rigs.json').read_text())
        deforms = json.loads((ROOT/'client_deforms.json').read_text())
        text = client_profiles.custom_header(model_audit.generate_header(rigs), 'ClientRigs')
        text = text.replace('namespace ClientRigs {', 'namespace ClientRigs {\nusing Stock::Rig;')
        self.assertEqual((ROOT/'native/ClientRigs.h').read_text(), text)
        text = client_profiles.custom_header(client_profiles.deform_audit.generate_header(deforms), 'ClientDeforms')
        text = text.replace('namespace ClientDeforms {', 'namespace ClientDeforms {\nusing Deform::Profile;\nusing Deform::Variant;')
        self.assertEqual((ROOT/'native/ClientDeforms.h').read_text(), text)
        for label in ('grimfall', 'sirus'):
            models = [m for m in rigs['models'].values() if m['client'] == label]
            self.assertGreaterEqual(len(models), 30)
            for race in model_audit.RACES:
                for sex in ('male', 'female'):
                    path = f'character/{race.lower()}/{sex}/{race.lower()}{sex}'
                    self.assertTrue(any(m['path'].replace('\\','/').replace('_hd.m2','.m2') == path+'.m2' for m in models), path)
        for model in rigs['models'].values():
            self.assertEqual(model_audit.select_rig(model), model['rig'])
        # Grimfall omits these filenames from its archive listfiles and old DBC joins.
        for race in ('darkirondwarf', 'lightforgeddraenei', 'zandalaritroll', 'dracthyr'):
            for sex in ('male', 'female'):
                path = f'character/{race}/{sex}/{race}{sex}.m2'
                for label in ('grimfall', 'sirus'):
                    self.assertTrue(any(m['client'] == label and m['path'].replace('\\', '/') == path
                                        for m in rigs['models'].values()), label + ':' + path)
                    self.assertTrue(any(m['client'] == label and m['path'] == path
                                        for m in deforms['models'].values()), label + ':' + path)
        dark_iron = [m for m in rigs['models'].values() if m['client'] == 'grimfall'
                     and m['path'].replace('\\', '/') == 'character/darkirondwarf/male/darkirondwarfmale.m2']
        self.assertEqual([(m['bone_count'], len(m['key_bones'])) for m in dark_iron], [(257, 289)])
        naga = [model for model in rigs['models'].values() if '/nagasirushd/' in model['path'].replace('\\','/')]
        self.assertEqual(len(naga), 2)
        for model in naga:
            self.assertEqual(model['rig']['upperlegs'], [-1, -1])
            self.assertGreaterEqual(model['rig']['hips'], 0)


if __name__ == '__main__':
    unittest.main()
