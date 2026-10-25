# `strata components install-file`（Strata Terminal CLI）

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査、commit 日 2026-10-25）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| 主な実装 | `strata_cli/update_cmd.py`、`strata_control/updater.py` |
| 位置引数 | `file` — ダウンロード済み engine package のパス |

## 役割

手元にある engine package を、ネットワークから取得せずにローカルへ導入します。初回起動時などに自分で取得した package を使う経路です。package の署名・全収録ファイル・この PC との適合性を確認し、新しい engine を隔離環境でテスト起動してから切り替えます（`strata_cli/update_cmd.py:59-61`、`strata_control/updater.py:1088-1091`）。

## 使い方

```sh
strata components install-file ./strata-engine-<version>-<platform>-<backend>.tar.gz

# 対話入力を使わず、機械可読な進捗と結果を得る
strata components install-file ./strata-engine-<version>-<platform>-<backend>.zip --wait 300 --output jsonl
```

`file` は必須です。コードが受け付ける拡張子は `.tar.gz`、`.tgz`、`.tar.xz`、`.zip` です（`strata_control/updater.py:1080-1085`）。

## 主な動作

1. `--components-dir` または既定の per-user component directory を使い、更新ロックを取得して作業用 staging directory を作ります。既定の場所は POSIX では `$XDG_DATA_HOME/strata/components`（未設定時は `~/.local/share/strata/components`）、Windows では `%LOCALAPPDATA%/Strata/components` です。`STRATA_COMPONENTS_DIR` があればそちらが優先されます（`strata_cli/update_cmd.py:185`、`strata_control/engine_component.py:176-190`）。
2. package を staging directory に展開し、engine manifest を読みます。組み込みの信頼鍵と `STRATA_UPDATE_TRUSTED_KEYS` で指定された追加鍵を使って署名を必須検証し、manifest が列挙する各ファイルのサイズ・SHA-256 などを照合します（`strata_cli/update_cmd.py:208-212`、`strata_control/signing.py:194-216`、`strata_control/updater.py:1097-1124`、`strata_control/engine_component.py:402-427`）。
3. OS、backend、engine runtime、GPU architecture、NVIDIA driver などの適合条件を確認します。`--backend` を指定すると検出した backend をその値で置き換えて判定します（`strata_cli/update_cmd.py:187-190`、`strata_control/updater.py:1125-1132`、`strata_control/feed.py:372-395`）。
4. `--model-config` があればその run config、なければ利用可能なインストール済みモデルの config を使い、隔離した runtime/profile/component directory でテストします。モデルが見つからない場合は engine の `--version` 起動確認になります。テスト成功後に engine を切り替え、以前の engine をロールバック用に保持し、古い engine を整理します（`strata_control/updater.py:707-723,878-930,995-1077`）。

この処理は `STRATA_NO_ACQUIRE` による取得禁止を確認する `acquisition.require()` より前の専用分岐で実行されます。通常の update と異なり feed を読み込まず、ネットワーク取得もしません（`strata_cli/update_cmd.py:208-218`）。指定した package ファイルは成功後も元の場所に残ります（`strata_control/updater.py:1088-1091,1070-1072`）。

## 実行モードと主な option

install-file 専用の実行モードはありません。`strata components install-file FILE` が検証・テスト起動・切り替えを行います。共通 parser の主な指定は次のとおりです（定義: `strata_cli/update_cmd.py:30-39,59-61`）。

| 指定 | 動作 |
| --- | --- |
| `--components-dir DIR` | component の保存先を指定します。省略時は環境変数または per-user 既定値を使います。 |
| `--backend FAMILY` | 適合性判定に使う backend を指定します。値の選択肢は parser で列挙されていません。 |
| `--model-config RUN_CONFIG.json` | テスト起動に使う config を指定します。省略時はインストール済みモデルから探索し、なければ `--version` のみを確認します。 |
| `--force` | 現在の engine より古い package でも導入処理を試します。省略時は古い package を導入せず、現在の engine を維持します。 |
| `--wait SECONDS` | engine が稼働中の場合に停止を待つ上限を指定します。省略時は対話 TTY で待機確認が表示され、JSON/非対話では待たずに busy エラーになります。 |
| `--output human\|json\|jsonl` | human が既定値です。json/jsonl は機械向け出力で、jsonl は進捗イベントも出力します。 |

`--feed` も共通 parser によって受理されますが、このコマンドの install-file 分岐は feed source を参照しないため効果はありません（`strata_cli/update_cmd.py:30-39,208-217`）。

## 注意点・失敗時

- package は署名必須です。未署名、信頼鍵がない、署名不正、manifest や収録ファイルの検証失敗は拒否されます。ファイルが読めない、拡張子が未対応、PC に合わない package、空き容量不足も導入前に失敗します（`strata_control/updater.py:1080-1132`）。
- 別 engine が serving 中なら、`--wait` の時間内に停止しない場合は busy として終了コード 7 になります。Strata の `launch` が使っている場合は停止が必要と通知します（`strata_cli/update_cmd.py:258-273`、`strata_control/updater.py:71-82,306-317`）。
- テスト起動失敗は終了コード 6 で、現在の engine は切り替わりません。切り替え後に新 engine が選択されない場合も旧 engine は維持され、終了コード 6 です（`strata_control/updater.py:85-128,1001-1024,1038-1055`）。
- 導入時は staging、engine directory、更新状態・履歴を書き換えます。成功すると active engine を更新し、旧 engine を rollback 用に保持し、それ以外の engine を整理することがあります。失敗時は staging を削除します（`strata_control/updater.py:1097-1100,1146-1148,1056-1077`）。
- `--force` は PC 適合性や署名検証を省略しません。また、install-file で明示的に確認できる効果は「現在より古い package の拒否を解除する」ことです（`strata_control/updater.py:1115-1132,1138-1145`）。

## 出力

human 出力では各処理 phase の案内と導入結果を表示します。`--output json` では結果または `{schema_version, ok: false, error: {code, message}}` 形式の失敗を出力します。`jsonl` では phase/waiting 等の進捗イベントに加え、最後に結果 JSON を出します。更新エラーはその error code を終了コードとして返し、署名エラーは 5、割り込みは 130 です（`strata_cli/update_cmd.py:65-87,174-183,208-217,246-255`）。

## 関連文書

- [CLI オプション索引](../../../README.md) — `strata components install-file` の option scope と個別文書。
- [`--backend`](--backend.md)、[`--components-dir`](--components-dir.md)、[`--force`](--force.md)、[`--model-config`](--model-config.md)、[`--output`](--output.md)、[`--wait`](--wait.md) — 個別 option 文書（索引に掲載された予定リンク）。

## 根拠

- `strata_cli/update_cmd.py:30-62,174-217,246-273` — parser、共通 option、install-file の分岐、出力・失敗・稼働中確認。
- `strata_control/updater.py:1080-1148` — archive 形式、展開・署名・適合性検証、version guard、staging の後始末。
- `strata_control/updater.py:878-930,995-1077` — engine のテスト起動、切り替え、履歴・rollback 用 engine の保持。
- `strata_control/engine_component.py:176-190,402-427` — component 保存先と manifest 対象ファイルの完全検証。
- `strata_control/signing.py:194-216`、`strata_control/feed.py:372-395` — 信頼鍵の読込と PC 適合条件。
- `strata_cli/cli.py:2135-2137` — top-level CLI から update command 実装への dispatch。

調査範囲は上記 commit のソースです。同一 revision の CLI `--help` は実行していません。Release artifact や各 OS/backend での実機導入結果は確認していません。
