# `strata components verify`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components verify` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/doctor.py` |
| 対象 | 保存済み profile または run-config JSON が参照するローカル component |

## 役割

インストール済み profile の run config を読み、推論エンジン、tokenizer、設定されたモデル関連ファイル、任意の monitor 依存などがローカルにあるかを読み取り専用で確認します。エンジンは起動しません。コマンドの parser は `--profile` を必須とし、説明を「installed profile に必要なファイルの確認」としています（`strata_cli/cli.py:114-119`）。確認処理は `strata_control.doctor.inspect` に委譲されます（`strata_cli/cli.py:1023-1028,2138-2139`）。

これはファイルの存在・種類・一部の実行可否を調べる inventory です。モデルや component の内容をハッシュ照合するものではなく、report の integrity は `unverified_no_manifest_hashes` と明記されます（`strata_control/doctor.py:223-235`）。

## 使い方

```sh
# 保存済み profile のローカル component を確認
strata components verify --profile four-gpu

# JSON report を取得
strata components verify --profile four-gpu --output json

# NVIDIA GPU の見える範囲も確認
strata components verify --profile four-gpu --live --output json
```

`--profile` には保存済み profile 名、または `.json` パス・絶対パス・パス区切りを含む run-config JSON の参照を渡せます。profile 名は保存 profile の `source_config` に解決され、パス形式の値は profile 名としては扱われません（`strata_control/profiles.py:382-388`）。run config は JSON object で、文字列配列 `args` と非空の `exe`、`tokenizer` パスを必要とします（`strata_control/profiles.py:135-147`）。

## 主な動作

- エンジン、tokenizer の `vocab.json`・`merges.txt`・`token_type.json`、run config の `args` が参照する既知のファイル／ディレクトリ、vision 設定があればそのファイルを検査します。ファイルは存在し、サイズが 0 より大きいこと、ディレクトリは directory であることを確認します。POSIX ではエンジンの実行権限も確認します（`strata_control/doctor.py:19-27,44-54,162-218`）。
- optional な monitor dependency は Textual の存在と version を確認します。未導入・version 不明・期待 version と不一致の場合は optional/unverified として報告し、これだけでは required component の欠落エラーになりません（`strata_control/doctor.py:254-273`）。
- required component の `missing` / `invalid` は error issue になります。Linux の HIP/SYCL では、該当する device node があり、いずれにも読み書きできない場合に device access warning を追加します（`strata_control/doctor.py:223-251`）。
- `--live` を付けると設定 backend と GPU 選択を使って live probe を追加します。CUDA 系では `nvidia-smi` を一度、5 秒 timeout で呼び出し、可視 NVIDIA device index と選択 index を比較します。未実装の HIP/SYCL 等 probe は error として `unverified` を返します。NVIDIA card 情報が得られて選択 GPU がない場合も `selection_unverified` であり、選択 device の一致を検証したことにはなりません（`strata_control/doctor.py:80-115,118-143,230-233`）。
- 通常の実行はファイルを読む／stat するだけで、engine を起動せず、修復・download はしません。`--live` の場合は外部の `nvidia-smi` を起動します。driver/card 情報は CUDA 互換性、PCIe topology、性能やモデル integrity を証明しません（`strata_control/doctor.py:80-93,146-235`、`docs/TERMINAL.md:158`）。

## 出力と失敗

既定の human 出力では component ごとの status・名前・path または理由を表示し、続けて issue を表示します。live probe が実行された場合は状態と取得できた NVIDIA card 情報も表示します。`--output json` は `{schema_version, ok, report}` 形式を stdout に出します（`strata_cli/cli.py:1023-1045`）。

report が成功なら終了コード 0、error issue がある場合は 5 です。profile/config の読込エラーなど `ValueError` は `_run` の共通経路でエラー出力され、例外に終了コードがあればそれを使います。profile の一般的な validation error は既定で 2、run-config を読めない場合は `ProfileError` が 5 を指定します。共通経路に到達した未処理の OS file operation error は 6 です（`strata_cli/cli.py:1045,2166-2183`; `strata_control/profiles.py:30-36,135-147`）。JSON mode ではエラーも JSON error object として出力されます（`strata_cli/cli.py:527-532,2166-2183`）。

## 注意点

- `--live` は `--profile` が必須のコマンド構造と組み合わさり、profile 固有の選択とホスト inventory を比較します。probe 不可・未実装の backend では必ずしも「GPU がない」という意味ではなく、確認できない理由が report に含まれます（`strata_cli/cli.py:116-119`; `strata_control/doctor.py:118-143`）。
- ファイルの存在確認は署名済み manifest による hash 検証や engine 実行試験ではありません。実行可能な engine file が見つかっても、backend 互換性や実際の推論成功は確認しません（`strata_control/doctor.py:162-179,223-235`; `docs/TERMINAL.md:158`）。
- `--quiet` は one-shot 共通処理で stdout を捕捉し、成功時の human 出力を抑えます。失敗して捕捉した出力があれば stderr に出します。JSON 出力時は quiet capture を通りません（`strata_cli/cli.py:508-515,2232-2248`）。

## 関連文書

- [Terminal CLI 索引](../../../README.md) — このコマンドと option 文書一覧。
- [`--profile`](--profile.md)、[`--live`](--live.md)、[`--output`](--output.md)、[`--json`](--json.md)、[`--quiet`](--quiet.md)、[`--help` / `-h`](--help.md)
- Strata `docs/TERMINAL_QUICKSTART.md:64-71` — component check の利用例。
- Strata `docs/TERMINAL.md:158` — inventory の範囲と制約。

## 調査範囲

上記は指定 revision の source checkout と同 revision 内の利用者向け文書に基づきます。CLI `--help` の実行と Release 配布物の照合は行っていません。GPU probe の実測、各 OS/backend の実機確認も行っていません。

## 根拠

- Strata `strata_cli/cli.py:114-119,508-515` — `components verify` parser と共通 `--json` / `--quiet` 登録。
- Strata `strata_cli/cli.py:1023-1045,2129-2139,2166-2183` — profile 解決、検査呼び出し、出力、終了コードと例外処理。
- Strata `strata_control/profiles.py:135-147,382-388` — run-config 検証と profile 名／JSON path の解決。
- Strata `strata_control/doctor.py:19-27,44-54,80-143,146-235,238-273` — component 検査、live probe、report、monitor dependency。
- Strata `docs/TERMINAL.md:158`、`docs/TERMINAL_QUICKSTART.md:64-71` — ユーザー向け説明と例。
