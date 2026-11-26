# `--mtp`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--mtp` |
| 別名 | なし |
| 値 | 通常のエンジン経路では MTP draft layer の runtime ディレクトリ。Qwen3.6 family の専用経路では draft 数 `0..7`。 |

## 役割

通常のエンジン経路では、MTP（multi-token prediction）draft layer の runtime ディレクトリを指定し、モデルの native head と組み合わせて speculative decoding の候補 token を作ります。Qwen3.6 family は `--native` の GGUF architecture によって専用 parser へ分岐するため、同じ `--mtp` でも意味が異なり、ディレクトリではなく GGUF 内蔵 MTP block の draft 数を指定します。

## 使い方

```sh
# 通常のエンジン経路: runtime ディレクトリを使い、4-token の speculative window を有効にする
strata --native model.gguf --tokens '1,2,3' --spec 4 --mtp /models/draft-rt

# Qwen3.6 family: GGUF 内蔵 MTP block から最大 4 draft を使う
strata --native qwen36.gguf --tokens '1,2,3' --mtp 4
```

## 値と既定値

- 通常経路の parser は次の引数を文字列として `o.mtp` に格納します。値の形式・ディレクトリの存在は parser では検証せず、空文字列を指定した場合は未指定と同じ扱いです。複数回指定した場合は parser loop が後の値で置き換えます（`engine/src/program/generate.cpp:3842-3847,4055`）。
- 通常経路では既定値は空（MTP layer を読み込まない）です。`--spec` の既定値は Metal 以外で `0`、Metal で `2` です。MTP は `--spec` が `2` 未満なら警告を stderr に出して無視されます。通常は `--spec 2` 以上を指定してください（`engine/src/program/generate.cpp:1010-1017,8243-8247`）。
- Qwen3.6 family では、値の先頭が数字なら `atoi` で draft 数として読み、範囲 `0..7` 以外は終了コード `2` で拒否します。先頭が数字でない値（例: runtime ディレクトリ）は無視して stderr に通知します。値の省略は parser の `needs a value` エラーで終了コード `2` です（`engine/src/qwen35/q36_engine.cu:5348-5353,5373-5379,5456`）。

## 実行時の動作

通常の CUDA/HIP 経路では、MTP runtime の `dense.txt` と `dense.bin` を読み込み、`experts.bin` のサイズを geometry から計算したサイズと照合して GPU に配置します。`experts.txt` があれば native expert format と geometry も検証します。MTP drafter は target model の canonical geometry を使い、speculative window に応じた draft layer state を用意します（`engine/src/core/mtp.cpp:345-408,410-485`; 呼び出し元 `engine/src/program/generate.cpp:8254-8265`）。

Metal 経路では `--mtp` の値を runtime ディレクトリとして受け取り、既定ではその親ディレクトリの `mtp-q2_0.gguf` を開きます。`STRATA_METAL_MTP_GGUF` が設定されていれば、その値を GGUF path として優先します（`engine/metal/src/engine/window.cpp:3705-3722`）。

runtime に token subset がある場合は既定で `<runtime>/draft_vocab.bin` を読み、draft head を subset に限定します。`--mtp-draft-vocab FILE` が別 path を明示すればそちらが使われます。subset がない・空の場合や `STRATA_MTP_FULL_HEAD=1` の場合は full head で drafting します（`engine/src/core/mtp.cpp:939-945,1007-1013`; path 選択 `engine/src/program/generate.cpp:6498-6499,8250-8253`）。

`--draft dflash2` と組み合わせる場合、既定の `--draft-fallback none` では `--mtp DIR` は MTP layer のロードには使われず、`DIR/draft_vocab.bin` を DFlash2 の vocabulary source として参照した後に通常経路の `o.mtp` を空にします。`--draft-fallback mtp` なら DFlash2 が起動できない場合に使う MTP layer もロードします（`engine/src/program/generate.cpp:6494-6530,8266-8326`）。

Qwen3.6 family では `--mtp N` は path を読む指定ではありません。`N > 0` の場合だけ GGUF 内の MTP block をロードするようにし、モデルに MTP block がないと実効 draft 数は `0` になります（`engine/src/qwen35/q36_engine.cu:5373-5379,5456-5462,5555-5559`）。

## 適用条件と副作用

- 通常経路では `--mtp` 単独で speculative decoding は有効にならず、`--spec 2` 以上が必要です。`--batch-mtp` を使う場合は `--serve`、`--batch 2` 以上、`--spec 2` 以上、MTP runtime が必要です。layer split の pipelined batch groups、Metal batch windows など未対応の組み合わせでは警告を出して slot MTP drafting を無効にします（`engine/src/program/generate.cpp:7841-7873`）。
- runtime の dense weights、512 routed experts、K/V state、draft head 等を GPU VRAM に確保します。通常経路ではメモリ不足も開始失敗の原因になります。単一 GPU / 条件を満たす split 経路では、空き GPU memory が不足する場合に警告を出して MTP layer を外し、draft なしで起動を続ける fallback があります（`engine/src/program/generate.cpp:8188-8217,8262-8265`; loader の allocation errors `engine/src/core/mtp.cpp:397-404,457-483,511-558`）。
- MTP runtime の loader はファイルを読み込むだけで、文書確認時点ではこの option によるファイルの書き換え・削除は確認できません。
- Qwen3.6 family の parser は、この値を MTP draft 数としてのみ扱います。数字以外で始まる値は path としてロードされず、警告付きで無視されます（`engine/src/qwen35/q36_engine.cu:5373-5379`）。

## 出力とエラー

- 通常経路で `--spec < 2` の場合、`strata generate: --mtp is ignored without --spec T (T >= 2)` を stderr に出し、`--mtp` をクリアして処理を続けます（`engine/src/program/generate.cpp:8243-8247`）。
- runtime の `dense.txt` / `dense.bin` / `experts.bin` が読めない、index が不正、experts サイズや native geometry が不一致、必要な tensor が欠ける、または GPU allocation に失敗した場合、loader が理由文字列を設定します。呼び出し元は `strata generate: ...` を stderr に出し、終了コード `1` で終了します（`engine/src/core/mtp.cpp:384-404,434-463,486-489`; `engine/src/program/generate.cpp:8264`）。
- Qwen3.6 family で `--mtp` の値が範囲外なら `strata-q36: --mtp takes 0 .. 7 drafts` を stderr に出し、終了コード `2` で終了します。非数値の値は無視され、エラー終了にはなりません（`engine/src/qwen35/q36_engine.cu:5373-5379,5456`）。

## 根拠

- `engine/src/program/generate.cpp:3804-3817,3842-3847,4055` — family 分岐と通常 parser の値取得・格納。
- `engine/src/program/generate.cpp:1010-1017,8243-8265` — `--spec` の初期値、spec 条件、通常経路での load。
- `engine/src/core/mtp.cpp:345-408,410-489,511-558` — runtime の読込、ファイル・形式・VRAM 検証。
- `engine/metal/src/engine/window.cpp:3705-3722,2498-2504` — Metal の GGUF path 解決と GGUF 読込。
- `engine/src/core/mtp.cpp:939-1013` — draft vocabulary subset と full-head fallback。
- `engine/src/program/generate.cpp:6494-6530,7841-7873,8188-8217` — DFlash2 との選択、batch 条件、VRAM 不足時の fallback。
- `engine/src/qwen35/q36_engine.cu:5339-5353,5373-5379,5456-5462,5555-5560` — family 分岐先の別 parser、draft 数と validation。
