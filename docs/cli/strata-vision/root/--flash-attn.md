# `--flash-attn`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。調査時の Strata checkout は `main`（`origin/main` と同期）で、working tree は clean。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision` / `strata-vision-hip` / `strata-vision-sycl` |
| オプション | `--flash-attn` |
| 別名 | なし |
| 値 | 値を1つ取る。`on` と `off` は個別に解釈し、それ以外の文字列は `auto` として扱う |

## 役割

画像エンコーダーが使う llama.cpp の multimodal context に Flash Attention の設定を渡します。ソースコメントでは `on` は K/V を FP16 で保持する経路、`off` は attention を FP32 で行う経路と説明されています (`tools/vision/strata_vision.cpp:117`)。これは `strata-vision` 系の独立実行ファイルのオプションで、Terminal CLI のサブコマンドではありません (`docs/cli/README.md:1511-1519`)。

## 使い方

```sh
strata-vision --mmproj vision-mmproj.gguf --model text-model.gguf --flash-attn off
```

`--mmproj` と `--model` はこの実行ファイルで必須です。ここではエンコーダー設定だけを示すため、画像処理要求を送る常駐プロトコル部分は省略しています (`tools/vision/strata_vision.cpp:7-8,125-128,283-291`)。

## 値と既定値

- `on` は `LLAMA_FLASH_ATTN_TYPE_ENABLED`、`off` は `LLAMA_FLASH_ATTN_TYPE_DISABLED` に変換されます。それ以外は `LLAMA_FLASH_ATTN_TYPE_AUTO` になります。値の大文字小文字や文字列の妥当性を検査する分岐はありません (`tools/vision/strata_vision.cpp:91-92,117-122`)。
- 省略時の初期値は `auto` です (`tools/vision/strata_vision.cpp:91`)。
- オプションを指定した場合は値が必須です。末尾に値がなければ `<option> needs a value` を stderr に出して exit 2 します (`tools/vision/strata_vision.cpp:95-98`)。
- 複数回指定した場合はループ中に値が順に代入され、最後の指定が残ります。少なくとも一度指定すると `fa_given` が true になります (`tools/vision/strata_vision.cpp:92-93,117-122`)。

## 実行時の動作

パーサーで決めた値は `mtmd_context_params` の `flash_attn_type` に設定され、画像エンコーダーの context 作成 `mtmd_init_from_file()` に渡されます (`tools/vision/strata_vision.cpp:214-224,231`)。

CPU 実行（`--gpu` なし）で、かつ `--flash-attn` を一度も指定せず、ビルドされた ggml が AVX-512 対応の場合は、初期値 `auto` が `DISABLED` に置き換わります (`tools/vision/strata_vision.cpp:132-140,218-224`)。明示的に `--flash-attn auto` と書くと `fa_given` が true になるため、この補正は行われず `AUTO` のまま渡されます。明示した `on` / `off` もこの補正より優先されます (`tools/vision/strata_vision.cpp:117-122,223-224`)。

`--gpu` を付けた場合はこの CPU / AVX-512 補正の条件から外れます。GPU 利用自体は `cp.use_gpu` に別途設定されます (`tools/vision/strata_vision.cpp:132-140,214-224`)。このオプションは context 作成時に適用されるため、常駐中に変更する経路は確認できません。

## 適用条件と副作用

CPU の `auto` は Flash Attention を有効にする、とソースコメントは説明しています。コメントによれば、この画像エンコーダーの head size は 72 で、AVX-512 の vector 幅の倍数ではないため、ggml が遅い fallback kernel を使い FP16 で累積する場合があります。未指定時の AVX-512 回避はこの CPU 経路に対する補正です (`tools/vision/strata_vision.cpp:218-224`)。同ファイルの性能値は特定の Ryzen 7 7700X でのコメント上の測定であり、他環境での性能を保証するものではありません。

CUDA / HIP / SYCL / Metal 等の個別 backend で各値がどう実装されるか、また不適切な値を `auto` にする llama.cpp 側の詳細は、この Strata parser と呼び出し箇所だけからは確認できません。ビルド時の backend 構成は `tools/vision/CMakeLists.txt:18-32,68-82` にあります。

## 出力とエラー

このオプション専用の警告やエラー出力は見当たりません。値なしは stderr と exit 2、未知の別引数は `unknown argument` と exit 2 です (`tools/vision/strata_vision.cpp:95-98,123`)。設定を渡した後に context を作れない場合は `ERR cannot load the vision encoder <mmproj>` を stdout に出して exit 1 しますが、この経路が `--flash-attn` の値に固有の失敗を示すわけではありません (`tools/vision/strata_vision.cpp:231-235`)。

## 根拠

- parser、初期値、値の変換、未指定時の AVX-512 条件、mtmd 設定への反映、context 作成失敗: `tools/vision/strata_vision.cpp:88-128,214-235`
- `--gpu` の初期値と CPU/GPU 条件: `tools/vision/strata_vision.cpp:89-90,130-140,214-224`
- backend build option: `tools/vision/CMakeLists.txt:18-32,68-82`
- tool-id、root scope と予定リンク: `docs/cli/README.md:1511-1525`
- 配置規約、ソース確認・値/副作用/エラー調査基準: `docs/cli/001_investigation.md:13-22,51-69,71-114`
