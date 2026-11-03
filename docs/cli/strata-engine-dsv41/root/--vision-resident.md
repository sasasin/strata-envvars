# `strata-dsv41 --vision-resident`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（root） |
| オプション | `--vision-resident` |
| 別名 | なし |
| 値 | 値なしのフラグ |

## 役割

`--serve` モードで画像 tower の device 側メモリを画像処理の合間にも GPU 上に保持します。通常の server 起動では、条件が満たされると tower の重みは host memory に置き、画像を encode するときだけ GPU memory を取り、画像処理後に返します。このフラグはその lazy 運用を無効にします（`src/dsv41/ds4_main.cpp:2506,2552,2620`、`src/dsv41/ds4_vision.cu:264-266`）。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --serve --vision-resident
```

`--pack` にはモデル pack のパスを指定します。`strata-dsv41` の root CLI は `--serve` を含む実行形を受け付けます（usage は `src/dsv41/ds4_main.cpp:115-123`、引数処理は `:2520,2582`）。

## 値と既定値

値は取りません。parser はこの引数を見つけると内部フラグ `vision_resident` を `true` にし、値を読みません（`src/dsv41/ds4_main.cpp:2506,2552`）。同じフラグの複数指定に対する個別のエラー処理はなく、いずれも同じ `true` を設定します。別の値を後ろに付けると値として消費されず、通常の引数として再解釈されます。未知の引数は usage を表示して終了コード 2 になります（同 `:2511-2519,2596-2599`）。

未指定時、`--serve` なら `--vision-resident` と `--vision-only` がないことを条件に `o.vision_lazy` が有効になります（同 `:2619-2620`）。ただし実際に lazy になるのは、後述の GPU・reserve 条件も満たす場合です。`--serve` 以外の通常推論・画像単体 encode では `o.vision_lazy` が false となるため、このフラグによる動作差はありません。

## 実行時の動作

model load 時、lazy が要求され、かつ先頭 GPU が integrated GPU でない場合に限り、`--reserve-mib` の値を tower の lazy 判定へ渡します。それ以外は `-1` を渡して device 側に保持します（`src/dsv41/ds4_model.cu:7732-7737`）。`VisionTower::load` は tower の device memory 使用量に 192 MiB の余裕を加えた量以上が reserve されている場合にだけ、device allocation を解放して lazy 状態にします（`src/dsv41/ds4_vision.cuh:40-42,63`、`src/dsv41/ds4_vision.cu:397-405`）。

したがって `--serve` で本フラグを指定すると lazy 判定自体が行われず、load した tower は常駐します。画像処理後の `vision_idle()` は lazy tower のみ device allocation を解放するため、常駐 tower では何もしません（`src/dsv41/ds4_main.cpp:1134`、`src/dsv41/ds4_model.cu:14963`、`src/dsv41/ds4_vision.cu:264-266`）。model load は vision tower を layer split より先に載せ、その後の split は残った GPU memory を見る実装です（`src/dsv41/ds4_model.cu:2813-2814,7738-7741`）。常駐指定時は tower が占有する分を他のモデル領域が使えません。

## 適用条件と副作用

- 効果があるのは server mode のみです。`--vision-lazy` は互換用として受け付けますが、同フラグ単独でも既定と同じ扱いであり、`--vision-resident` と併記しても後者を打ち消しません。parser は `--vision-lazy` を別の未使用変数に記録するだけで、最終設定は `serve_mode && !vision_resident && !vision_only` で決まります（`src/dsv41/ds4_main.cpp:2506,2552-2553,2619-2620`）。
- `--vision off` を併用すると vision tower の load 自体がスキップされるため、常駐指定の対象がありません（同 `:2551`、`src/dsv41/ds4_model.cu:2814`）。pack に vision tower がない場合も `load_vision` は tower を持たないまま成功します（同 `:7694-7698`）。
- GPU memory を追加で確保するオプションではありません。常駐 tower の初期 load に失敗した場合、model は警告を stderr に出し、画像を無効にしてテキストのみで続行します（`src/dsv41/ds4_model.cu:2814-2822`）。
- 本フラグを使わない lazy server では、画像処理時に GPU memory の取得を試み、必要なら expert slot を一時借用します。取得を数回試しても失敗すると画像 encode はエラーになります。この失敗メッセージでは `--vision-resident` が tower を GPU に保持する選択肢として案内されます（`src/dsv41/ds4_vision.cu:494-530`）。常駐指定が GPU memory 不足を解消するとの保証はありません。

## 出力とエラー

本フラグ固有の出力や validation error はありません。`--vision` が有効で tower を load できない場合の警告と text-only fallback は前節のとおりです（`src/dsv41/ds4_model.cu:2814-2822`）。通常の未知引数は stderr に `unknown option ...` と usage を出し、終了コード 2 です（`src/dsv41/ds4_main.cpp:2596-2599`）。

## 調査範囲

同一 revision の parser、model load、vision tower の確保・解放経路を確認しました。実機での GPU memory 量、性能差、各 GPU/backend での実測挙動は調査していません。

## 根拠

- parser・既定条件・usage: `src/dsv41/ds4_main.cpp:115-123,2500-2519,2551-2553,2582,2596-2625`
- vision load の条件と reserve 判定: `src/dsv41/ds4_model.cu:2813-2822,7694-7701,7732-7754`
- resident/lazy memory 管理・画像時の再取得: `src/dsv41/ds4_vision.cuh:40-63`、`src/dsv41/ds4_vision.cu:264-266,397-405,494-530`
- server の画像処理後の解放呼び出し: `src/dsv41/ds4_main.cpp:1102-1144`、`src/dsv41/ds4_model.cu:14960-14965`
