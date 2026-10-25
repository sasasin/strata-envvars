# `--embd-gguf`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata` |
| オプション | `--embd-gguf PATH` |
| 別名 | なし |
| 値 | トークン埋め込み `token_embd.weight` を含む GGUF ファイルのパス |

## 役割

ネイティブ（IQ）expert pack を使う実行で、トークン埋め込みを `--native` のモデル GGUF からではなく、指定した GGUF から読み込みます。主な用途は、BF16 や Q6_K などの埋め込みを専用ファイルに分けて読み込ませることです。埋め込みテーブルは token ID から各 token の行を取り出す経路で使われます（`src/program/generate.cpp:477-478, 3753-3772`、`src/core/layer.cpp:1322-1327`）。

## 使い方

```sh
strata --pack /models/native-pack --native /models/model-00001-of-00002.gguf \
  --spec 2 --prefill 128 --embd-gguf /models/token-embd-bf16.gguf
```

これは既存の native pack とモデル GGUF を使う場合の引数例です。native pack では `--native` に加えて `--spec` を2以上にし、複数 token の prompt なら `--prefill` に正の chunk を指定する必要があります。実行時には pack の種類も検査されます（`src/program/generate.cpp:3753-3767`）。

## 値と既定値

- parser は次の argv 要素を値として受け取り、文字列で保持します。数値変換やパス形式の事前検査はありません（CUDA/HIP系: `src/program/generate.cpp:2416-2421, 2500-2503`、SYCL系: `sycl/src/program/generate.cpp:1841-1844`）。
- オプションを省略するか、値が空文字列なら、native pack で `--native` から解決したモデル shard 群を使います。空でない値なら、そのパスだけを GGUF 入力としてロードします（`src/program/generate.cpp:3762-3763`、SYCL系: `sycl/src/program/generate.cpp:2847-2849`）。
- 同じオプションを複数回指定したときは各値を同じ文字列変数へ代入するため、最後の値が残ります（`src/program/generate.cpp:2502`）。
- 指定先には `token_embd.weight` が必要です。engine の形状 `[n_embd, n_vocab]` と一致し、GPU の embedding dequantizer が扱える型で、`n_embd` が256の倍数であることをロード時に検査します。型判定は IQ 型、BF16（GGML type 30）、Q6_K（type 14）を受け付けます（`src/core/native_head.cpp:130-137`、`src/kernels/cuda/iq_kernels.cu:4176-4178`）。
- payload が GGUF の範囲内にあり、計算した byte 数と一致することも検査します（`src/core/native_head.cpp:139-147`）。

## 実行時の動作

この値は parser で受理されても、埋め込みロードに使われるのは expert layout が native pack と判定された場合だけです。native pack では `--native` が必須で、`--spec >= 2`、`--keep-canonical` なし、複数 token の入力なら `--prefill` chunk が必要です。条件を満たした後、指定した GGUF（値が空なら `--native` の shard 群）から埋め込みを読み込み、native embedding として登録します（`src/program/generate.cpp:3510, 3753-3767`）。

ロードしたテーブルは通常の token 埋め込み経路と verifier 経路で token 行の gather に使われ、MTP / DFlash2 も同じ native embedding が登録されていればそれを参照します（`src/core/layer.cpp:1322-1327`、`src/core/verify.cpp:1204-1207`、`src/core/mtp.cpp:892-902`、`src/core/dflash2.cpp:283-294`）。native pack では通常の weight table 側の `token_embd.weight` は読み飛ばされます（`src/program/generate.cpp:3791`）。

指定した別 GGUF の architecture metadata は、`general.architecture` が `strata-embd` ならその値として受理され、それ以外は engine の対応 architecture 検査に通る必要があります。そのうえで必要な tensor 名・形状・型を検査します（`src/core/native_head.cpp:123-137`）。

## 適用条件と副作用

- native pack でない実行では、この値は埋め込みロードには使われません。別 GGUF の読み込み・検証も行われません。セッション識別情報を組み立てる経路では値が任意の embedding 入力として記録対象に渡されます（`src/program/generate.cpp:3753-3767, 9399-9413`、`src/core/conversation_file.cpp:930-940`）。
- `--native` の GGUF が Qwen3.6-35B-A3B family と判定される build では、通常 parser より先に Qwen3.6 専用 parser へ引数列ごと委譲されます。その parser は `--embd-gguf` を受理しません。通常実行では usage を表示して終了コード2、`--serve` では未知 option として警告し、直後の値が `--` で始まらなければ値と一緒に無視します（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3742-3749, 3782-3795`）。
- GPU gather のため GGUF の埋め込み payload 全体を GPU mapped host allocation にコピーします。確保できないときは VRAM にコピーする fallback があり、その場合 stderr に警告が出ます。fallback も失敗するとロードエラーです（`src/core/native_head.cpp:148-169`）。HIP では mapped host allocation の device alias を取得できない場合も VRAM fallback を試しますが、CUDA系では alias の取得失敗がロード失敗になります（`src/core/native_head.cpp:170-195`）。
- `tools/embd_bf16_pack.py` は BF16 の `token_embd.weight` を持つ一 tensor GGUF を作る用途として説明されています。元チェックポイントの BF16 をコピーする方法と、GGUF tensor を BF16 に変換する方法があります。生成物を既存ファイルへ書き出すツール側の副作用は、この CLI オプション自体の動作とは別です（`tools/embd_bf16_pack.py:1-15, 95-135`）。

## 出力とエラー

- 値がない場合は parser の `--embd-gguf needs a value` を stderr に出して終了コード2で終了します（`src/program/generate.cpp:2418-2421, 2502`）。
- native pack の前提を満たさない場合は要件を stderr に出して終了コード2です（`src/program/generate.cpp:3754-3759`）。
- 入力 GGUF の読込例外、非対応 architecture、tensor の欠落・形状不一致・非対応型、payload の切り詰めはエラーになり、呼び出し元は `strata generate: <理由>` を stderr に出して終了コード1で返します（`src/core/native_head.cpp:123-147, 202-204`、`src/program/generate.cpp:3762-3765`）。
- 未知オプションは `unknown argument: ...` と usage を stderr に出して終了コード2になります（`src/program/generate.cpp:2787-2792`）。

## 根拠

- parser、既定の空文字列、help 表示: `src/program/generate.cpp:477-478, 861-862, 2416-2421, 2500-2503`。SYCL parser: `sycl/src/program/generate.cpp:460-461, 790, 1841-1844`。
- 入力選択、適用条件、ロード結果のログ: `src/program/generate.cpp:3510, 3753-3772`。SYCL loader 呼び出し: `sycl/src/program/generate.cpp:2839-2858`。
- Qwen3.6 family の早期委譲と別 parser の unknown-option 処理: `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3742-3795`。
- GGUF / tensor 検証とメモリ確保: `src/core/native_head.cpp:123-205`。
- 型の対応条件: `src/kernels/cuda/iq_kernels.cu:4176-4178`。
- token 行の利用: `src/core/layer.cpp:1322-1327`、`src/core/verify.cpp:1204-1207`、`src/core/mtp.cpp:892-902`、`src/core/dflash2.cpp:283-294`。
- 調査したのは指定 revision の checkout 内の parser と実装です。ビルド済み CLI の `--help` と Release artifact は照合していません。
