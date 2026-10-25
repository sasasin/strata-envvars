# `STRATA_ROUTE_RESIDENT_RANKS`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_ROUTE_RESIDENT` が有効なとき、resident bias の候補となる top-10 の順位範囲を指定します。順位は 0 始まりです。既定値 `6-9` は top-10 の後ろ4枠を対象にします。この変数単独では routing を有効にしません。

CUDA verifier の routing 後に、指定範囲内で非 resident expert を resident expert に置き換えます。MTP draft router でも、`STRATA_ROUTE_RESIDENT_MTP` が有効な場合に同じ順位範囲を使います。いずれも選択 expert と重みを変える可能性があります。

## 値と判定

実装は `sscanf(value, "%d-%d", &lo, &hi)` を使い、変換できた整数を更新します。文字列全体の検証や値域の clamp はありません。各読み取り箇所の初期値は `lo=6`, `hi=9` です。

| 値 | 結果 |
|---|---|
| unset、空文字、先頭が整数でない文字列 | 変換なしなら初期値 `6-9` のまま |
| `2-5` | `lo=2`, `hi=5` |
| `2-x` | 最初の整数だけ変換し、`lo=2`, `hi=9` |
| `x-5` | 最初の変換に失敗するため `6-9` のまま |
| `2-5junk` | `2-5` を読み取り、後続文字列は検査しない |
| `-2-5` | `%d` の符号として読み、`lo=-2`, `hi=5` |

先頭の空白は `%d` の変換規則に従います。`%d-%d` が返す変換数は呼び出し元で検査されません。数値の大小関係や、負値、`hi >= 10` などの入力範囲も検証しません。

## 有効になる条件

- verifier 経路では `STRATA_ROUTE_RESIDENT` を `atof` した margin が `0.0` より大きく、expert 数 `NE == 512`、top-k `K == 10`、resident table `hits_.d_res` が存在するときだけ適用されます。`STRATA_ROUTE_RESIDENT_RANKS` を設定しても、これらの条件を満たさなければ何も変わりません。
- MTP 経路では `use_mtp` が真、layer stages が空（single-GPU 経路）、resident table が存在し、`STRATA_ROUTE_RESIDENT` が設定済みで、`STRATA_ROUTE_RESIDENT_MTP` の `atoi` 結果が非ゼロであることが必要です。さらに margin が正で、MTP 側も 512 experts / top-10 の場合に適用されます。
- どちらの経路も `lo > hi` なら順位ループは実行されません。`hi` が 10 以上でも `r < 10` で止まります。負の `lo` は下限で除外されず、kernel 内の top-10 配列の範囲外順位を参照し得るため、有効な設定として扱えません。

## 実行時の詳細

verifier は `route_resident_cfg()` の関数内 static 初期化で、`STRATA_ROUTE_RESIDENT` とこの変数を一度読み取り、結果をプロセス内で保持します。初期化後に環境を書き換えても verifier の値は変わりません。設定値は、router が ids / weights を出した後、resident plan や doorbell 処理より前に native kernel へ渡されます。

kernel は順位 `lo` から `hi`（ただし 9 以下）を順に調べます。その順位の選択 expert が非 resident なら、まだ選択されていない resident expert のうち logit が最大のものを探し、元の expert との logit 差が margin 以下のとき置換します。置換が一度でも起きると、選択後10件の logits から weights を再計算します。MTP 経路でも同じ native kernel と範囲を使います。

MTP の設定読み取りは generation の初期化経路で行われ、ここでは `lo=6`, `hi=9` をローカル初期値として直接 `getenv` / `sscanf` します。条件を満たして適用すると stderr に `strata generate: STRATA_ROUTE_RESIDENT_MTP: ... ranks %d-%d; experimental` のログが出ます。verifier は終了時に統計を出し、ログにも `ranks=lo-hi` を含めます。

## 根拠

- 既定値、verifier の static cache、値の変換: `src/core/verify.cpp:71-76,123-131`。
- verifier の呼び出し時点と適用条件: `src/core/verify.cpp:1464-1475`。
- verifier の終了時統計ログ: `src/core/verify.cpp:99-116`。
- MTP 経路の条件、既定値、読み取り、ログ: `src/program/generate.cpp:7440-7454`。
- MTP router での native kernel 呼び出し: `src/core/mtp.cpp:927-930`。
- 順位ループ、resident expert の探索、置換判定、重み再計算: `src/kernels/cuda/native_router.cu:180-184,192-255`。
- `docs/DETAILS.md:1663` は `STRATA_ROUTE_RESIDENT` を opt-in の関連機能として挙げていますが、`STRATA_ROUTE_RESIDENT_RANKS` の形式や挙動は説明していません。上記の値の規則は対象 HEAD の実装から確認しました。
