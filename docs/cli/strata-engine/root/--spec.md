# `--spec`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | CMake 生成の通常推論エンジン `strata`（引数 parser の root） |
| オプション | `--spec` |
| 別名 | なし |
| 値 | 整数 `N`（`atoi` で変換）。推論検証窓の幅を指定 |

## 役割

推論時に一度に検証する speculative decoding の窓幅を指定します。窓は直前の確定 token と draft token を含む `N` token で、`N=0` は通常の一 token ずつの decode です。MTP draft layer を使う場合、`--mtp` と `--spec 2` 以上を指定すると MTP が窓用の候補を生成します。MTP を指定しない場合も、正の値は speculative loop を有効にし、既定で有効な suffix prompt lookup が条件に合う繰り返し候補を供給できます（`src/program/generate.cpp:650-657, 16091-16102, 16408-16429`）。

## 使い方

```sh
strata --pack /path/to/pack --tokens-file prompt.txt --mtp /path/to/mtp/runtime --spec 4
```

これは通常 engine parser の引数例です。`--pack`、入力 token、MTP runtime の指定は実際の利用環境に合わせてください（`src/program/generate.cpp:2423-2444, 2607-2624`）。

## 値と既定値

- parser は `--spec` の次の argv を `std::atoi` で整数化し、`Options::spec` に代入します。数値形式や範囲を検証する分岐はこの parser にありません。省略時は Metal build で `2`、それ以外で `0` です（`src/program/generate.cpp:650-657, 2607-2609`）。
- `0` は通常 decode です。MTP を指定しても `N < 2` なら MTP 指定は無視され、その旨を stderr に出します。native (IQ) pack は `N >= 2` を必要条件とし、満たさない場合は診断して終了コード `2` で終了します（`src/program/generate.cpp:3753-3760, 5455-5459`）。
- 窓の verifier が扱う定数上限は 8 です（`include/strata/kernels/verify_kernels.hpp:21`）。parser は `--spec` の値そのものを 8 以下へ一般的に制限しません。値が大きい場合の処理は組み合わせや後続初期化に依存するため、8 以下を指定してください。
- ヘルプ文は setup が設定値 `4` を書くことに触れていますが、これは parser の既定値ではありません（`src/program/generate.cpp:938-941`）。
- 同じ引数列で複数回指定すると parser loop が各値を順に代入するため、最後に読まれた値が残ります（`src/program/generate.cpp:2416-2421, 2607-2609`）。

## 実行時の動作

- prompt の最後から通常の token loop を切り替える条件は `N > 0` です。speculative loop では窓幅分の buffer と `DraftPolicy` を用意し、検証窓の一致した draft を確定します（`src/program/generate.cpp:16080-16102, 16381-16429`）。
- `--suffix-draft` は既定で `3` です。`N >= 2`、suffix draft が有効、かつ `--mtp-max-t` が未指定（0）のとき、元の `N` を MTP の上限に保存したうえで verifier の窓を最大 `N+2`、上限 8 まで拡張します。`--mtp-max-t` を指定するとこの自動拡張分岐は行われません（`src/program/generate.cpp:776-779, 3205-3210`）。
- `--lookup-chain K` が正で `N >= 2` のとき、MTP 窓の後ろに lookup 候補を足せるよう verifier 窓を拡張し、最大 8 に抑えます。suffix draft による拡張が先に行われる場合は、その後の幅を基準に計算します（`src/program/generate.cpp:780-783, 3212-3219`）。
- `--mtp` を指定して `N < 2` の場合、MTP はクリアされて読み込まれません。`N >= 2` なら MTP runtime を読み込み、窓幅（pipeline windows が 2 以上なら固定上限幅）を使って draft を生成します（`src/program/generate.cpp:5455-5473`）。
- `--draft dflash2` が利用可能で、対象 GPU に応じた cap が実際の `N` より小さい場合、engine は警告を出して `N` をその cap に変更します。`--draft-cap` の指定は cap の選択に関与します（`src/program/generate.cpp:5474-5503`）。
- native pack は `N >= 2` を要求します。serve の pipeline windows と batch MTP は MTP と `N >= 2` を条件にし、pipeline windows は条件不成立なら理由を出して off にします。一方、serve の prefill-window 経路自体は `N >= 2` と `--prefill CHUNK` を要求しますが、MTP は任意で、候補がなければ suffix lookup または通常 decode に fallback します（`src/program/generate.cpp:3753-3760, 4246-4288, 5301-5306, 8354-8366`）。

## 適用条件と副作用

- 窓幅を広げると verifier や draft 用 buffer のサイズ・処理幅が変わります。server の batch MTP では `N` に応じた residual buffer を各 slot に GPU allocate し、確保失敗時はエラーを出して終了コード `1` になります（`src/program/generate.cpp:9182-9195`）。
- Qwen3.6 family model は通常 parser に入る前に family 用 `run` へ委譲されます。この文書は通常 `src/program/generate.cpp` parser の scope であり、family 専用 parser の同名フラグの意味を含みません（`src/program/generate.cpp:2393-2407`）。索引では別 scope の [`qwen36` option 文書](../../qwen36/README.md)を案内しています。
- parser は数値の変換・範囲を検査しないため、無効な文字列は `atoi` の結果 `0` として扱われ得ます。負値も parser では拒否されません。値の妥当性を caller が期待する前提で使わず、整数 `0`〜`8` の範囲を指定してください（`src/program/generate.cpp:2607-2609`, `include/strata/kernels/verify_kernels.hpp:21`）。

## 出力とエラー

- `--spec` の値が欠けている場合、共通の値取得処理が `--spec needs a value` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2416-2421, 2607-2609`）。
- MTP が `N < 2` で無視される場合は stderr に `--mtp is ignored without --spec T (T >= 2)` を出します。native pack の必要条件に違反した場合は `strata generate: ... needs --spec T (T >= 2)` を出して `2` を返します（`src/program/generate.cpp:3755-3760, 5455-5459`）。
- MTP runtime のロード失敗はエラー文字列を stderr に出して `1` を返します（`src/program/generate.cpp:5470-5473`）。その他の backend／値での失敗条件を網羅する実行確認は行っていません。

## 根拠

- parser 既定値と型: `src/program/generate.cpp:650-657`
- parser の値取得・代入・不足値経路: `src/program/generate.cpp:2416-2421, 2607-2609`
- ヘルプ上の説明: `src/program/generate.cpp:935-941`
- suffix / lookup による窓幅変更: `src/program/generate.cpp:3205-3219`
- speculative loop と draft policy: `src/program/generate.cpp:16091-16102, 16408-16429`
- MTP／native pack／serve の適用条件: `src/program/generate.cpp:3753-3760, 5455-5473, 8355-8365`
- verifier の窓上限: `include/strata/kernels/verify_kernels.hpp:21`
