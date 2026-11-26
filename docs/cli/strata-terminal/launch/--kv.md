# `--kv`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--kv FORMAT` |
| 別名 | なし |
| 値 | `int8`、`q4_0`、`k8v4`、`fp16`、`fp8`、`k8v8` |

## 役割

会話履歴を保持する K/V cache の形式を指定する。設定は選択したモデル family の setup 処理またはエンジン引数へ渡るため、同じ値でも適用可能な形式、未指定時の形式、利用メモリは family と backend によって異なる。

## 使い方

```sh
strata launch --model iq3_xxs --context 128k --kv q4_0
```

モデルを指定せず preset の設定を上書きする場合:

```sh
strata launch --preset "IQ3_XXS 128K" --kv q4_0
```

## 値と既定値

`--kv` は値を1つ取る。値は前後の空白を除去して小文字化した後に検証されるため、大文字小文字は区別されない。値を省略した場合は `LaunchSettings.kv` が `None` のままになり、選択した family の既定処理に委ねられる。`strata launch` 自体で一律の既定形式を固定してはいない。

| 値 | 受理と適用 |
| --- | --- |
| `int8`、`q4_0`、`k8v4`、`fp16`、`fp8`、`k8v8` | `strata launch` parser が受理する値。実際に使われる形式は下記の family/backend 条件に従う。 |
| 未指定 | preset に同じ設定があればその値を使い、なければ family の既定処理に委ねる。 |
| その他の値 | parser が拒否し、選択可能な値を示す引数エラーになる。 |

## 実行時の動作

`--preset` を指定すると保存済み設定を読み込み、明示した `--kv` があればその値で上書きする。値は起動設定に入り、モデルに応じて setup 用引数、または生成するエンジン設定へ反映される。通常の Flash-Next 系 setup は、context が 8K を超える場合は `int8`、それ以外は `fp16` を基本とし、明示値があればそれを優先する。setup は低 VRAM 条件でも `int8` を選ぶ。`strata launch` から setup を呼ぶ経路では `--yes` が渡るため、setup の対話式 KV 選択は行わない。（`terminal/strata_cli/launch/cmd.py:215-250`、`terminal/strata_cli/launch/settings.py:122-135`、`terminal/strata_cli/launch/runner.py:323-354,1358-1374`、`terminal/setup.py:12189-12203`）

転送後の扱いは family によって異なる。

| モデル / backend | 適用される動作 |
| --- | --- |
| Flash-Next 系 | setup の `--kv` が受け取る形式は同じ6種類。未指定時は context と GPU 条件に基づく既定値を使う。8K 超で対話 setup を直接実行する場合は選択画面があるが、`strata launch` の setup 呼び出しは `--yes` を付ける。 |
| Qwen3.6 | setup は `fp32`、`fp16`、`fp8`、`fp4` を使う。Terminal parser が受理するうち `fp16` と `fp8` は転送される。`int8`、`q4_0`、`k8v4`、`k8v8` は Flash-Next 用形式として警告され、Qwen3.6 の既定 `fp32` に戻る。 |
| Hy4-Flash | `strata launch` は native `.strata` family への setup 引数として `--kv` を渡さず、設定プレビューでも native engine 分岐で K/V 値を追加しない。したがって、このコマンド経由では指定値は適用されない。setup.py を直接呼ぶ場合は Flash-Next 用設定として無視する旨の警告が出る。 |
| Inkling-2-Mini / CUDA | `fp16`、`fp8`、`k8v8`、`k8v4` をエンジンへ渡す。`int8` と `q4_0` は Inkling の形式ではないため、警告して engine の既定動作に委ねる。 |
| Inkling-2-Mini / HIP・Metal・SYCL | `fp16`、`fp8` を渡す。`k8v4` と `k8v8` は backend がサポートしないため、警告して `fp8` に置き換える。`int8` と `q4_0` は Inkling の形式ではないため、警告して engine の既定動作に委ねる。 |

Inkling engine は K/V dtype を自動選択する設定が既定で、`--parallel` が16以上なら、形式を明示していない場合に `fp8` を選ぶ。明示した対応形式は自動選択を無効にする。K/V 形式は slot ごとの cache 割り当てに影響し、Inkling engine は要求された slot 数について K/V cache を割り当てる。（`terminal/strata_cli/launch/settings.py:38-73`、`terminal/strata_cli/launch/runner.py:329-347,760-785,1363-1374,2219-2223`、`engine/src/inkling2/ink_backend.h:33-34`、`engine/src/inkling2/ink_main.cpp:882-892,1021-1024`、`engine/src/inkling2/ink_batch.h:16-20,33-36`、`engine/src/inkling2/ink_serve.h:541-546`）

## 適用条件と副作用

K/V 形式によって cache のメモリ量が変わる。Inkling の実装上、1 token あたりの Global K/V cache は `fp16` が32 KiB、`fp8` が16 KiB、`k8v8` が16.5 KiB、`k8v4` が12.75 KiB。これらの割り当てはモデル起動時に発生する。数値は Inkling engine の実装値であり、他 family にそのまま当てはまるとは限らない。（`engine/src/inkling2/ink_batch.h:16-20,147-149`）

`--kv` 自体がファイルを作成・削除する処理は確認できない。起動時には launch の実行設定が private config として保存されるため、その設定に選択値が含まれる。`--save-preset` を併用した場合は起動成功後に設定を preset として保存する。（`terminal/strata_cli/launch/runner.py:2234-2238`、`terminal/strata_cli/launch/cmd.py:952-964`）

## 出力とエラー

- 6種類以外の値は parser の型変換で拒否され、選択可能な値を含むエラーになる。未登録のオプション名は `strata launch` の未知オプションとして標準エラーに表示され、終了コード `2` で終了する。（`terminal/strata_cli/launch/cmd.py:35-43,186-201`、`terminal/strata_cli/cli.py:2325-2334`）
- Inkling でサポートされない形式や backend 非対応形式を指定すると、launch の設定処理が標準の警告として通知する。前者は engine の既定動作を使い、後者は `fp8` へ置換する。（`terminal/strata_cli/launch/settings.py:61-74`、`terminal/strata_cli/launch/runner.py:2219-2223`）
- Inkling engine 自身に渡る不正な `--kv` 値は標準エラーへ許容値を表示し、終了コード `2` で終了する。ただし Terminal の `strata launch` parser が受理する6値のうち Inkling 非対応の値は、Terminal が事前に除外して警告するため、この engine エラー経路には渡らない。（`engine/src/inkling2/ink_main.cpp:882-892`）

## 根拠

- `terminal/strata_cli/launch/cmd.py:35-43,73-93` — `--kv` の parser、値変換、選択肢。
- `terminal/strata_cli/launch/cmd.py:215-250` — preset 読み込みと CLI 値の上書き。
- `terminal/strata_cli/launch/settings.py:38-73,122-135` — 共通値、Inkling backend ごとの対応値、未指定状態と警告文。
- `terminal/strata_cli/launch/runner.py:323-354,760-785,1358-1374,2219-2238` — family 別の反映、Inkling の警告、設定ファイル保存。
- `terminal/setup.py:9911-9913,10328-10329,12189-12203` — Qwen3.6 / Hy4 の扱い、Flash-Next 系の既定値と対話選択。
- `engine/src/inkling2/ink_main.cpp:882-892,1021-1024` — Inkling engine の受理形式と `--parallel` に応じた自動選択。
- `engine/src/inkling2/ink_batch.h:16-20,33-36,147-149`、`engine/src/inkling2/ink_serve.h:541-546` — Inkling の各形式の cache サイズ、backend 対応範囲、slot 割り当て。

調査範囲は上記の Terminal parser、launch の設定・転送経路、参照される setup と Inkling engine の処理。各 GPU driver の実際の割り当て量や実行性能は測定していない。
