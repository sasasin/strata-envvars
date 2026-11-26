# `--kv`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`./setup.sh` / `START-HERE.bat` 経由を含む） |
| オプション | `--kv` |
| 別名 | なし |
| 値 | `int8`、`q4_0`、`k8v4`、`fp16`、`fp8`、`k8v8` のいずれか |

## 役割

モデルの会話履歴を保持する KV cache の形式を指定する。setup が選んだ値は、対象 family の設定に応じて起動設定へ書かれ、engine に渡される。値の意味と受理範囲は family / engine によって異なるため、setup parser が受理する6値すべてを、すべてのモデルで使用できるわけではない。

## 使い方

Linux でモデルをセットアップし、コンテキスト長が8Kを超える場合に4-bit KVを指定する例:

```sh
./setup.sh --model 8B --context 32768 --kv q4_0 --no-start
```

`--kv` は値を1つ取る。`setup.sh` は `terminal/setup.py` に引数を転送し、Windows の `START-HERE.bat` も同じ `setup.py` に引数を渡す（`setup.sh:6-17`、`START-HERE.bat:53-64`）。

## 値と既定値

- parser の `choices` は `int8`、`q4_0`、`k8v4`、`fp16`、`fp8`、`k8v8`。省略時は `None` で、構文上のデフォルト値は設定されていない（`terminal/setup.py:11460-11462`）。選択肢以外の値は `argparse` が拒否する。重複指定の独自処理はなく、標準 parser は最後に指定された値を `a.kv` に設定する（同ファイル `:11444`、`:11606`）。
- 通常の Flash-Next 系では、context が8Kを超えるか、VRAMが少ない条件なら既定は `int8`、それ以外は `fp16`。context が8Kを超え、`--yes` を付けず `--kv` を省略した場合は対話選択があり、既定選択は `int8`。VRAM条件は全モデルで12.5 GB以下、または Unsloth model で16.5 GB以下（context 64K以上なら24.5 GB以下）（`terminal/setup.py:12190-12205`）。
- `q4_0` は4-bit、`int8` は8-bit、`k8v4` はINT8 K + 4-bit V、`fp16` は16-bitとして通常系の説明とメモリ計算に使われる（`terminal/setup.py:11460-11462`、`:302-303`、`:8804`）。

## 実行時の動作

- 通常の Flash-Next 系では選択値を使ってセットアップ設定の `args` を作る。context が8K超、または選んだ形式が `fp16` 以外なら `--kv <値>` を engine 起動引数に加える（`terminal/strata_control/setup_config.py:218-225`）。低VRAM Unsloth向けの起動見積もりが不足する場合は、ユーザーが `--kv` を明示していなければ、起動可能性を高める候補に変更することがある。明示指定時は `kv_fixed` としてその形式を保持する（同ファイル `:378-400`）。
- 通常系の engine `strata generate` は `fp16`、`int8`、`q4_0`、`k8v4` のみを有効値として検証し、KV実装の形式切替に使う（`engine/src/program/generate.cpp:3906`、`:5014-5020`）。したがって parser が受理する `fp8` / `k8v8` は、この通常系には適合しない。これらを通常系で指定すると setup parser では通るが、生成された設定を使う engine 起動時に拒否される。
- Qwen3.6 の own-path 分岐は `fp32`、`fp16`、`fp8`、`fp4` を専用形式として扱う。setup parser が受理した値のうち `fp16` と `fp8` は転送し、`int8` / `q4_0` / `k8v4` / `k8v8` は警告を表示して既定の `fp32` に任せる。一方、`fp32` / `fp4` は説明上の対応形式でも setup parser の choices にないため、このCLIから指定できない（`terminal/setup.py:9911-9913`、`:9984-9988`、`:11460-11462`）。
- Inkling-2-Mini では `fp16` / `fp8` / `k8v8` / `k8v4` だけを転送する。HIP / Metal / SYCL backend で `k8v8` または `k8v4` を指定すると警告して `fp8` に置き換える。ほかの parser 受理値はこの分岐では黙って転送対象外となる（`terminal/setup.py:10891-10897`）。
- `--kv-streaming` が有効になる通常系では、選んだ KV 形式を使ってRAM必要量を見積もり、64K以上のcontextで条件を満たすと `--kv-resident 32768` を追加する。これは `--kv` の形式とは別の配置制御で、WSLではstreamingしない（`terminal/strata_control/setup_config.py:301-332`）。
- 以前の設定を新しいcheckoutへ引き継ぐ場合、通常系は保存済み `--kv` のうち `int8` / `q4_0` のみ再利用する。Qwen3.6、Hy4-Flash、Inkling-2-Mini は own-path扱いでKV値を引き継がない（`terminal/setup.py:7808-7825`、`:11702-11710`）。

## 適用条件と副作用

- Apple Silicon の通常モデルは `setup.py` の parser に入る前に `metal/setup_mac.py` へ委譲されるため、この root parser の `--kv` は使えない。Hy4-Flash / Inkling-2-Mini はこの委譲を迂回する経路がある（`terminal/setup.py:11435-11437`）。
- 既存モデルを単に起動する実行では `--kv` は保存済み設定を変更せず、指定されると「モデルの再セットアップ時だけ有効」と警告される。変更するには `--setup --model ... --kv ...` が必要（`terminal/setup.py:11734-11739`）。
- セットアップは起動設定を書き、通常は起動スクリプトを作る。`--no-start` を併用した例はセットアップ後の自動起動を抑止する（設定生成とスクリプト作成は `terminal/setup.py:12521-12527`、終了分岐は同ファイル `:12555-12556`）。

## 出力とエラー

- 通常系で8K超のcontextを指定した場合、選択したKV形式を `KV cache: ...` として表示する（`terminal/setup.py:12204-12205`）。
- parser の choices 外の値は `argparse` のエラーとなる（parser 定義と `parse_args()` は `terminal/setup.py:11460-11462`、`:11606`）。通常系のengineが非対応値を受けた場合は `strata generate: --kv must be fp16, int8, q4_0 or k8v4` を stderr に出し、終了コード2を返す（`engine/src/program/generate.cpp:5014-5017`）。
- Qwen3.6 でFlash-Next形式を指定した場合、および Inklingの指定値が backend 非対応の場合は、setup が警告を表示して既定値または `fp8` に切り替える（`terminal/setup.py:9911-9913`、`:10892-10897`）。

## 根拠

- parser と選択値: `terminal/setup.py:11444-11462`。
- 通常系の既定値と対話選択: `terminal/setup.py:12190-12205`。
- 通常系の設定引数への反映、KV streaming、低VRAM補正: `terminal/strata_control/setup_config.py:218-225`、`:301-332`、`:378-400`。
- 通常系engineの受理値と検証: `engine/src/program/generate.cpp:3906`、`:5014-5020`。
- Qwen3.6 / Inkling固有の値処理: `terminal/setup.py:9911-9913`、`:9984-9988`、`:10891-10897`。
- wrapperとMac委譲: `setup.sh:6-17`、`START-HERE.bat:53-64`、`terminal/setup.py:11435-11437`。

調査時点のcheckoutは `git status --short --branch` で `## main...origin/main` と表示され、未コミット変更は確認されなかった。実行時のengine引数以降の効果は、Strata内の各engine実装が確認できた範囲に限って記載した。
