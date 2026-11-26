# `strata --lookup-max-t`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。主に `--serve`） |
| オプション | `--lookup-max-t` |
| 別名 | なし |
| 値 | 非負整数 `N`。prompt-lookup の窓長上限。`0` は無効 |

## 役割

suffix drafter がプロンプト中の過去の一致箇所から候補トークンを提案するとき、MTP の窓とは別に、検証窓を最大 `N` トークンまで広げられるようにします。各候補窓サイズは draft policy が候補の一致長や窓のコストを見て選び、提案トークンは通常どおり verifier で検証されます。`--lookup-sizes` は上限内で使うサイズを絞る設定です（`engine/src/program/generate.cpp:1168-1175, 1507-1528, 22715-22740`、`engine/src/spec/draft_policy.cpp:577-615`）。

## 使い方

```sh
# serve で prompt-lookup の窓上限を明示する
strata --serve --native "$MODEL" --mtp "$MTP" --spec 4 --lookup-max-t 12

# 明示的に無効にする
strata --serve --native "$MODEL" --mtp "$MTP" --spec 4 --lookup-max-t 0
```

## 値と既定値

- parser は次の引数を `std::atoi` で整数化し、`std::max(0, ...)` を適用します。負数は `0` になり、数値として読めない文字列も `atoi` の結果により `0` になります。複数回指定時は後の値が同じフィールドを上書きします。値が欠けている場合は stderr に `--lookup-max-t needs a value` を出して終了コード `2` で終了します（`engine/src/program/generate.cpp:3842-3847, 4121-4124`）。
- オプションを省略した場合だけ `STRATA_LOOKUP_MAX_T` などの条件から既定値を決めます。環境変数が設定され、その先頭文字が `0` なら既定値を無効化します。それ以外では、窓が 8 行の build、非 Metal、serve、単一 GPU、layer split なし、`--batch` なし、DFlash2 でない、lookup chain なし、suffix drafting 有効、`--spec >= 2` の全条件を満たすと `12`、それ以外は `0` です（`engine/src/program/generate.cpp:5040-5055`、`engine/include/strata/core/lookup_default.hpp:9-28`）。
- 明示値も実際に利用できる長さは build の `kVerifyLongT` と `--spec` によって制限されます。8 行 build では `kVerifyLongT` は 16、12 行 build では 12、16 行 build では 16 です（8 行以下では 2 倍、それより広い build では build 幅）。lookup が有効で suffix drafting も有効かつ `--spec >= 2` の場合、エンジンは MTP 用の `mtp_max_t` を保持しつつ `spec` を最大 `min(N, kVerifyLongT)` まで広げます（`engine/include/strata/kernels/verify_kernels.hpp:23-31`、`engine/src/program/generate.cpp:5079-5098`）。したがって `N` は実行窓の長さそのものではなく上限です。

## 実行時の動作

有効な場合、`lookup_size_mask` は MTP のサイズと、既定では MTP サイズより大きい候補（MTP+1、MTP+2、上限）を policy に許可します。`--lookup-sizes` を指定すると追加候補はそのリストに置き換わり、`2..--spec` の範囲に入る数値だけが採用されます。サイズ選択は過去の一致長と測定・推定コストに基づくため、上限サイズが毎回使われるわけではありません（`engine/src/program/generate.cpp:1510-1528, 16401-16412, 16429-16431`、`engine/src/spec/draft_policy.cpp:577-615`）。

serve 起動時、`N > 0` なら stderr に有効な上限、MTP 窓長、許可サイズを表示します。プロンプト読込と生成の両方で選ばれた窓サイズの graph を準備します。VRAM 不足ならそのサイズを policy から外し、より小さい許可サイズへ下げます。VRAM 不足以外の graph 準備エラーは prompt 読込を失敗させるか、生成時に `ERR ...` を stdout に出して終了コード `1` になります（`engine/src/program/generate.cpp:16512-16529, 20432-20447, 22737-22740`）。

## 適用条件と副作用

- 既定で `12` になる条件は限定されています。特に Metal、幅の広い窓の build、複数 GPU、layer split、`--batch`、DFlash2、`--lookup-chain` のいずれかでは既定値は `0` です。これは省略時の既定値条件であり、明示値は別途 parser に受理されます（`engine/include/strata/core/lookup_default.hpp:23-28`）。
- `STRATA_GDN_SPLIT=1` のとき `N` が build の `kVerifyMaxT` より大きいと、値の由来で処理を分けます。GPU architecture default が設定した値なら環境変数を解除して広い窓を維持し、stderr に警告します。ユーザーが設定した値なら `N` を `kVerifyMaxT` にクランプし、stderr に警告します。どちらもこの条件だけでは終了しません（`engine/src/program/generate.cpp:5056-5077`、`engine/include/strata/core/nv_defaults.hpp:56-74`）。
- layer split の serve は窓を narrow 上限に抑えます。batch / pipelined windows も `kVerifyMaxT` を超えないとソースに記載されています（`engine/src/program/generate.cpp:13257-13262`、`engine/include/strata/kernels/verify_kernels.hpp:26-31`）。
- 各窓サイズの graph は VRAM を使い、ソースの usage は追加サイズあたり約 20–35 MiB と説明しています。この数値は実機での保証値ではありません（`engine/src/program/generate.cpp:1346-1348`）。

## 出力とエラー

- 引数値の形式や上限について、このオプション専用の validation error はありません。欠落値は終了コード `2`、負値・不正な数値文字列は `0` として扱われます（`engine/src/program/generate.cpp:3844-3846, 4123`）。
- GDN 分割との整合時は stderr に、既定 switch の解除または指定値のクランプを説明する警告を出します（`engine/src/program/generate.cpp:5063-5076`）。
- 窓 graph の VRAM 不足は窓サイズを無効化して縮小します。その他の graph 準備失敗はエラー経路になります（`engine/src/program/generate.cpp:16518-16529, 22737-22740`）。

## 根拠

- `engine/src/program/generate.cpp:1168-1175` — option 状態とコメント上の意味。
- `engine/src/program/generate.cpp:1346-1348, 3842-3849, 4121-4124` — usage、値取得、parser。
- `engine/include/strata/core/lookup_default.hpp:9-28` — 省略時既定値の条件。
- `engine/src/program/generate.cpp:5040-5098` — 環境変数、build / GDN 条件、実効上限。
- `engine/src/program/generate.cpp:1510-1528, 16401-16431, 16512-16529, 20432-20447, 22715-22740` — サイズ policy、serve の出力、prompt/decode 利用と失敗経路。
- `engine/src/spec/draft_policy.cpp:577-615` — lookup 候補のコスト比較と選択。
- `engine/include/strata/kernels/verify_kernels.hpp:23-31` — build の窓上限と長窓上限。
- `engine/src/program/generate.cpp:5056-5077`、`engine/include/strata/core/nv_defaults.hpp:56-74` — `STRATA_GDN_SPLIT` の扱い。
