# `--no-fused-gr`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--no-fused-gr` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

native GR の fused hyper-connection read を無効にし、A/B 比較用に通常の GR read と独立した write を使わせます。これは速度や出力品質を保証する設定ではなく、実行経路を切り替える診断用フラグです。`generate.cpp` の usage は「native の six-kernel hyper-connection read と separate write」と説明しています（`src/program/generate.cpp:958-960`）。

## 使い方

通常の native 経路で、モデルの native shard とトークン列を指定する例です。`SHARD1` とトークン ID は実際のファイル・入力に置き換えます。

```sh
strata --native SHARD1 --tokens 1,2,3 --no-fused-gr
```

`--native` は native 系の複数機能を有効にし、その中で `gr_native_mmvf` も有効化します（`src/program/generate.cpp:3263-3267`）。

## 値と既定値

値は不要です。parser は `Options::no_fused_gr` を `false` で初期化し、指定されると `true` にします。同じフラグを複数回指定しても同じ bool 値への代入が繰り返されるだけです。値の型変換や範囲検証はありません（`src/program/generate.cpp:601-608, 2780-2786`）。

未指定なら、このフラグによる無効化は行いません。ただし fused 経路そのものが常に既定で有効という意味ではありません。初期化時に `gr_native_mmvf` が true であり、かつ `--no-fused-gr`、`--gpu-stages`、`--dump-layers`、`--dump-halves`、`--stage-timing` のいずれも fused を止める条件に当たらない場合だけ、レイヤー側の fused GR を有効にします（`src/program/generate.cpp:3922-3932`）。

## 実行時の動作

parser は `--no-fused-gr` を受け取ると `o.no_fused_gr = true` とします（`src/program/generate.cpp:2780-2783`）。engine 初期化時には次の条件式の結果を `layer_set_fused_gr` に渡します。

```text
gr_native_mmvf
&& !no_fused_gr
&& !gpu_stages
&& dump_layers が空
&& dump_halves が空
&& !stage_timing
```

従って `--gr-native-mmvf` または `--native` と併用したときに fused GR を抑止する指定です。これらを有効にせず、他にも fused 経路を有効にする設定がなければ、このフラグ単体で実行経路は変わりません（`src/program/generate.cpp:3922-3932`）。

レイヤー実行側はさらに `stage_prefix == 0`、`half == 0` と GR 形状の `fused_gr_supported(...)` を条件として fused read を選びます。fused read の場合は `fused_gr_read` を使い、別経路では `gr_read` を呼び、その後の `gr_write` を独立して実行します。後段でも fused が無効なら `gr_write` を実行します（`src/core/layer.cpp:1477-1479, 1534-1550, 1557-1569, 1615-1627`）。形状が fused 対応外なら、フラグの有無にかかわらず fused 経路は使われません。

`STRATA_HC_REQ8=1` は GR down/up 投影を int8 + scale にします。`--no-fused-gr` と同時に単一 GPU のこの環境変数を使うと、unfused 側の GR read が `q8_scale` を検出し、`STRATA_HC_REQ8 needs the fused hyper-connection read` を返してレイヤー処理を失敗させます。`STRATA_HC_REQ8` は multi-GPU layer split では BF16 に戻されるため、この失敗条件は同変数が実際に有効な単一 GPU 経路に限ります（`src/program/generate.cpp:3843-3851`; `src/core/layer.cpp:1543-1545, 1566-1568`）。

## 適用条件と副作用

- `--gpu-stages`、`--dump-layers`、`--dump-halves`、`--stage-timing` も fused GR を無効にするため、それらと併用しても追加の切り替えはありません（`src/program/generate.cpp:3924-3931`）。
- 起動時に fused GR の bool を設定します。ソース上、このオプション自身はファイルやネットワークを操作せず、別プロセスも起動しません。
- `no_fused_gr` はセッション設定 fingerprint の switch にも含まれます（`src/program/generate.cpp:9450-9462`）。
- Qwen3.6 の GGUF は通常 parser の引数処理より前に専用 `qwen35::run` へ振り分けられます（`src/program/generate.cpp:2393-2407`）。専用 parser は `--no-fused-gr` を持たず、通常実行では未対応引数として usage を出して終了コード 2、`--serve` 中は未対応引数を警告して無視します（`src/qwen35/q36_engine.cu:3742-3795`）。Qwen3.6 ではこの文書の切り替え効果はありません。

## 出力とエラー

通常 parser はこのフラグ自体について警告・成功メッセージを出しません。未知の引数は `unknown argument: ...` と usage を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2787-2792`）。

`STRATA_HC_REQ8` の上記競合では GR read がエラー文字列を返し、呼び出し元の layer 処理が失敗します。CLI の最終表示と終了コードは、その後の実行経路に依存するため、このオプション固有の一律な終了コードとしては確認できません（`src/core/layer.cpp:1543-1545, 1566-1568`）。

## 根拠

- 索引の配置・scope: `docs/cli/README.md:1128-1134, 1223-1230`。この文書は `strata-engine/root/` の `strata` エンジン引数 parser の項目です。
- parser の help 表示、既定値、受理処理、未知引数経路: `src/program/generate.cpp:958-960, 601-608, 2780-2792`。
- `--native` が native GR を有効にする処理と fused 有効条件: `src/program/generate.cpp:3263-3267, 3922-3932`。
- fused / unfused のレイヤー経路、形状条件、Q8 失敗条件: `src/core/layer.cpp:1477-1479, 1534-1550, 1557-1569, 1615-1627`。
- Qwen3.6 専用 parser への振り分けと未対応引数の処理: `src/program/generate.cpp:2393-2407`, `src/qwen35/q36_engine.cu:3742-3795`。
- 調査時の Strata checkout は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`main...origin/main` で未コミット変更の表示はありませんでした。CLI help の実行、ビルド、GPU 実行、テストは行っていません。
