# `DF2B_MMAV`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal 同梱ベンチマーク `metal/tests/df2_bench.cpp` の fragment-order Q4_0 行列積チェックで、実行する Metal kernel 名の末尾と dispatch サイズを指定します。通常の Strata エンジン、サーバー、モデル実行からの読み取りは見つかりません。このため利用者向けの実行時設定ではなく、このベンチマーク専用の環境変数です。

## 値と判定

`main()` の開始後に `getenv()` で一度読み、値が未設定なら文字列 `2_4` を使います。設定時は文字列全体を比較・検証せず、そのまま保持します。空文字も設定済みとして空文字列が使われ、既定値には戻りません。CLI 引数による上書きはありません。

値は `DF2B_MMAK`（未設定時 `df2_mma4`）と連結され、kernel 名 `<DF2B_MMAK>_<DF2B_MMAV>` になります。さらに `%d_%d` 形式の `sscanf` で2つの整数 `R`, `S` を読み、dispatch grid と threadgroup サイズの計算に使います。`sscanf` の戻り値を確認せず、数値範囲の検査や clamp もありません。したがって、たとえば `2_4tail` は先頭の `2_4` を読み取れます。一方、空文字・形式不一致・片方だけ変換できる文字列では `R` / `S` の一部または全部が未初期化のまま使われ、動作は未定義です。数値として読める値でも範囲外を拒否する処理はありません。

## 有効になる条件

値が dispatch に使われるのは `DF2B_KIND` の値が文字列全体で `frag` と一致する場合だけです。この経路は fragment-order の Q4_0 データを作り、指定 kernel で GPU 計算し、CPU 参照値との誤差を比較します。`DF2B_KIND` が未設定、空文字、`mma`、その他の値の場合、この変数は読み取られますが、`mmav` を使う fragment-order dispatch 部分には入りません。

ベンチマーク側のコードに OS/backend/ビルド macro による追加の値切替、別環境変数からの優先上書き、設定値の警告はありません。`DF2B_MMAK=df2_mma4s` の場合だけ split-K 用の grid 式を選びますが、`DF2B_MMAV` 自体の優先順位は変わりません。

## 実行時の詳細

fragment-order 経路では `DF2B_MMAV` を `R` / `S` に分解し、`DF2B_MMAK + "_" + DF2B_MMAV` を `Context::pipeline()` に渡します。`R` と `S` はそれぞれ grid のタイル数および `tg[0] = 32 * S` に使われます。`DF2B_MMAK` が `df2_mma4s` なら grid 計算は split-K 用の式になります。計算後は GPU 結果と CPU 参照の差を出力し、`maxe >= 2e-3 * maxv` の場合は終了コード 1 で終了します。

要求した kernel 関数が Metal library にない場合、`metal/src/mtl_rt.mm` は stderr に `mtl: no function <名前> <説明>` を出して終了コード 3 で終了します。環境変数を読み取ったこと自体を示すログはありません。値は `main()` 内で一度だけ取得されるため、実行中の環境変更を再読込する経路はありません。

## 根拠

- `metal/tests/df2_bench.cpp:62-68` — ベンチマークの `main()` と `DF2B_KIND=frag` の判定。
- `metal/tests/df2_bench.cpp:195-197` — `DF2B_MMAV` と `DF2B_MMAK` の読み取り、既定値、split-K 判定。
- `metal/tests/df2_bench.cpp:213-240` — fragment-order 経路、`sscanf` による分解、kernel 名の組み立て、dispatch サイズ、比較失敗時の終了コード。
- `metal/src/mtl_rt.mm:484-510` — pipeline 関数の検索失敗時の stderr と終了コード 3。
