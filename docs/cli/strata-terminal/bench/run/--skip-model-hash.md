# `--skip-model-hash`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--skip-model-hash` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

`standard-v1` の実行時に、サーバーが使用しているモデルファイルの SHA-256 計算を省略します。モデルファイルのハッシュを省くと、生成される標準ベンチマーク結果は `nonconforming` として記録されます（parser: `strata_cli/cli.py:333-334`; 実行: `strata_cli/cli.py:1302-1305`; status 判定: `strata_cli/bench_standard.py:805-809,825-829,893-897`）。

## 使い方

```sh
strata bench run --url http://127.0.0.1:8000 --skip-model-hash
```

`--profile` と `--url` のいずれか一方は必須です。上の例はローカル HTTP server URL を指定しています（`strata_cli/cli.py:293-300`）。

## 値と既定値

- 値は不要です。`argparse` の `store_true` なので、省略時は `False`（モデルファイルをハッシュする）、指定時は `True`（ハッシュしない）です（`strata_cli/cli.py:333-334`）。
- 引数値、数値範囲、複数指定に対する個別 validation はありません。直後に値を置く形式ではなく、余分な位置引数は parser の未認識引数エラーになります（`strata_cli/cli.py:2223-2231`）。

## 実行時の動作

標準 suite の処理は `hash_model=not a.skip_model_hash` を `bench_standard.run()` に渡します（`strata_cli/cli.py:1302-1305`）。runner は server の `/props` の `model_path` と launch plan の engine 引数を候補にモデルファイルを探します。通常は既存の `.gguf`、`.safetensors`、`.pack`、`.bin` ファイルを対象にし、分割 GGUF なら存在する shard も対象にします（`strata_cli/bench_standard.py:805-809`; `strata_cli/bench_facts.py:393-411`）。

このフラグが有効だと候補一覧を空にして、各モデルファイルに対する SHA-256 読み取りを行いません。通常時はファイルごとに進捗をログ出力し、SHA-256 を計算して `results.json` の `model.files` にパス名と digest を記録します（`strata_cli/bench_standard.py:807-809`; `strata_cli/bench_facts.py:99-104,422-432`）。skip 時には `model.files` が `null` となり、`missing` にファイルをハッシュできなかった理由が記録されます。さらに `reasons_nonconforming` に `no model file could be hashed` が加わり、run status は `nonconforming` になります。リクエストの測定自体はこの理由だけでは中断されません（`strata_cli/bench_standard.py:825-829,845-849,893-897,953-960`）。

## 適用条件と副作用

`standard-v1` が既定 suite であり、このフラグの動作は標準プロトコル実行に限られます（`strata_cli/cli.py:297-300,1183-1188`）。他の serving suite でも共通 parser の引数として受理されますが、その経路は `a.skip_model_hash` を参照せず `bench.run()` に引き渡さないため、指定してもモデルファイル hash の挙動は変わりません（`strata_cli/cli.py:1186-1198,1221-1225`）。

このフラグはモデルファイルの読み取り・hash 計算だけを抑止します。標準 benchmark の workload、server 接続、モデルのロード、他の report artifact の生成時に行う artifact hash は制御しません（`strata_cli/bench_standard.py:807-809,899-906`）。通常実行でモデルファイルを読めない場合の `OSError` は CLI の共通エラー処理へ進み、終了コード 6 になります。skip 指定時はモデルファイルを読む処理を通らないため、そのファイル読取に由来する失敗は避けられます（`strata_cli/bench_facts.py:99-104,425-427`; `strata_cli/cli.py:2176-2183`）。

## 出力とエラー

- 標準 suite では skip 指定後も benchmark report を作成し、`results.json` の `run.status` は `nonconforming`、`extensions.status_reasons` に `no model file could be hashed`、`missing` の `/model/files` に欠落理由を記録します（`strata_cli/bench_standard.py:825-829,928-959`）。通常の標準 suite 完了経路では status が `complete` でないため CLI は終了コード 6 を返します（`strata_cli/cli.py:1312-1328`）。
- hash 対象ファイルの読取エラーは `OSError` として CLI のエラー処理に渡され、エラー出力と終了コード 6 になります（`strata_cli/bench_facts.py:99-104,425-427`; `strata_cli/cli.py:2176-2183`）。
- serving suite ではこのフラグによるエラーや hash 省略は発生せず、レポート status は serving suite 固有の判定によります（`strata_cli/cli.py:1186-1198,1221-1234`）。

## 根拠

- `strata_cli/cli.py:297-300,333-334` — コマンドの suite 既定値と `store_true` parser 定義。
- `strata_cli/cli.py:1183-1198,1221-1225,1302-1305` — standard / serving suite の分岐と hash 設定の受け渡し。
- `strata_cli/bench_standard.py:805-809,825-829,893-897,928-960` — モデルファイル列挙、nonconforming 判定、レポート記録。
- `strata_cli/bench_facts.py:99-104,393-411,422-442` — SHA-256 計算、候補ファイルと shard の列挙、model block の生成。
- `strata_cli/cli.py:2176-2183` — ファイル読取など `OSError` の共通エラー出力と終了コード。
