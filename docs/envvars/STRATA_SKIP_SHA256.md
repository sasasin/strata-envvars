# `STRATA_SKIP_SHA256`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`terminal/setup.py` がダウンロードした既製エンジンの zip を検証する `verify_engine_archive()` で、GitHub 公開 SHA-256 による検証を省略するための環境変数。値が文字列 `"1"` の場合、警告を出して関数から戻り、アーカイブを展開・インストールする処理へ進む。ソース上では同じ早期 return により公開サイズの比較と GitHub API からの digest 取得も省略される。したがって、この値はハッシュ計算だけを飛ばすものではない（`terminal/setup.py:6138-6147`）。

対象はセットアップ／更新が平置きの既製エンジン zip を取得して `verify_engine_archive()` を呼ぶ経路。通常の CUDA、CUDA 12 と Windows HIP がそれぞれこの関数を呼ぶ（`terminal/setup.py:5451-5455`, `terminal/setup.py:6351-6357`）。モデルファイルの検証やエンジンの実行時挙動を制御する変数ではない。

## 値と判定

`os.environ.get("STRATA_SKIP_SHA256") == "1"` による文字列全体の完全一致で、数値変換・trim・大文字小文字変換はない。空文字も未設定と同様に分岐を通らず、通常の検証を行う（`terminal/setup.py:6138-6147`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `verify_engine_archive()` が呼ばれるとき | SHA-256 検証を試みる | `1` | 空文字、`0`、`true`、`TRUE`、` 1`、`1 `、`01`、`1anything` など、文字列 `1` と異なる値 |

優先順位を変える CLI 引数はない。`--prebuilt` / `STRATA_PREBUILT_URL` は取得元を選ぶが、この変数の文字列判定を上書きしない（`terminal/setup.py:6295-6302`, `terminal/setup.py:11546-11551`）。

## 有効になる条件

- セットアップまたは更新が既製エンジンの平置き zip をダウンロードし、`verify_engine_archive()` に到達すること。
- 通常の CUDA / CUDA 12 では `--build` が指定されておらず、既製エンジン取得が選ばれること（`terminal/setup.py:9597-9625`）。Windows HIP では `--build` なしで既製 HIP zip を取得する経路であること（`terminal/setup.py:9606-9612`）。
- `--update` は古い既製エンジンの置き換えが必要になり、平置き zip を取得する場合に限る。更新対象が既に現行であれば早期 return し、feed からエンジンを取得する場合はこの変数を読む検証関数に入らない（`terminal/setup.py:6511-6549`, `terminal/setup.py:5435-5455`, `terminal/setup.py:6332-6357`）。
- OS/backend に固有の分岐は、Windows の HIP とその他の `get_prebuilt()` 経路。署名付き更新 feed のコンポーネント取得、ローカルビルド、既にインストール済みのエンジンをそのまま使う経路には適用されない（`terminal/setup.py:5374-5411`, `terminal/setup.py:6295-6303`, `terminal/setup.py:9597-9625`）。

## 実行時の詳細

`verify_engine_archive()` が呼ばれるたびに、関数内で現在の `os.environ` を読む。モジュール読み込み時の定数化やキャッシュはないため、同一プロセス内で環境値が関数呼び出し前に変更されれば、その呼び出しは変更後の値で判定される（`terminal/setup.py:6138`）。判定のタイミングは zip の取得後、展開前（`terminal/setup.py:5451-5459`, `terminal/setup.py:6351-6362`）。

値が `"1"` なら警告を出して検証関数を抜け、呼び出し元は zip を展開して後続の形式・エンジン metadata・version・GPU 対応確認を続ける。値がそれ以外なら GitHub Releases API から asset のサイズと `sha256:` digest を取得し、両方が得られたときにサイズを比較してから SHA-256 を計算する。サイズ不一致または hash 不一致ではダウンロードと `.done` 印を削除し `UnverifiedEngine` を送出する。初回導入では setup を終了し、更新では既存エンジンを維持する。API から digest を得られない場合は別の警告を出して検証なしで続行する（`terminal/setup.py:6083-6094`, `terminal/setup.py:6142-6164`, `terminal/setup.py:6167-6181`）。

`--prebuilt` のローカルフォルダーや GitHub Releases 以外の mirror は公開 digest がないため、通常値でも「digest が取れない」分岐で警告して進む。`STRATA_SKIP_SHA256=1` の場合はその取得も行わず、変数専用の警告に置き換わる（`terminal/setup.py:6047-6051`, `terminal/setup.py:6079-6094`, `terminal/setup.py:6138-6147`）。

## ログと測定値

値が `"1"` のときの警告本文は次のとおり。`warn()` は `[!]` を付けて stdout に表示し、JSONL 出力時は warning event も出す（`terminal/setup.py:6138-6141`, `terminal/setup.py:1044-1046`）。

> `STRATA_SKIP_SHA256=1: NOT checking {asset} against its SHA-256. If the file is corrupt or tampered with, it will be installed anyway. Unset it to get the check back.`

値が `"1"` でない場合、digest が取れなければ `could not get a SHA-256 for {asset} from GitHub (offline, rate limited, or not a release URL), so it was NOT verified. Installing it as it is.` と警告する。検証成功時は `SHA-256 checksum verified against GitHub's (...)` を表示する（`terminal/setup.py:6142-6146`, `terminal/setup.py:6160-6164`）。

`docs/SAFETY.md:140-142` と `docs/TROUBLESHOOTING.md:101-105` はこの変数をチェック無効化として説明している。実装では早期 return がサイズ比較より前にあるため、`"1"` は公開サイズ照合も飛ばす。性能値の記載はない。

## 根拠

- `terminal/setup.py:6138-6147` — 環境値の完全一致判定、警告、早期 return、通常の digest 取得。
- `terminal/setup.py:6148-6164` — 公開サイズと SHA-256 の照合、成功ログ。
- `terminal/setup.py:6167-6181` — 不一致時の初回導入／更新時の結果。
- `terminal/setup.py:5451-5459`, `terminal/setup.py:6351-6362` — Windows HIP と CUDA 系の呼び出し、検証後の展開。
- `terminal/setup.py:5374-5411` — 署名付き feed からエンジンを取得する別経路。
- `terminal/setup.py:9597-9625`, `terminal/setup.py:6511-6549` — 通常セットアップと更新の既製エンジン取得条件。
- `terminal/setup.py:1044-1046` — 警告の表示先と JSONL event。
