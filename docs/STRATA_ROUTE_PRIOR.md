# `STRATA_ROUTE_PRIOR`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（`2026-10-13` 時点）。

## 役割

verify window のルーターが選んだ専門家 top-10 を、VRAM に在駐する専門家を優先するボーナス付きスコアで選び直す。値はボーナス `lambda` として使われ、候補選択が変わるため、出力に影響する opt-in の実験的な設定である。通常の専門家ルーティング全般や prompt 処理を切り替える設定ではない。

## 値と判定

| 環境変数の状態・値 | コード上の扱い |
|---|---|
| 未設定 | `0.0f`。再選択しない。 |
| 空文字、数値として読めない文字列 | `std::atof` の結果は `0` となり、再選択しない。 |
| 数値文字列 | `atof` が変換した `float` をボーナスとして使う。値が `0` 以下なら再選択しない。正の値なら適用条件を満たすと再選択する。 |
| 数値の後ろに文字が続く文字列 | 変換終了位置を検査しないため、`atof` が読める先頭の数値部分が使われる。 |
| 負数・ゼロ | 解析されても `route_prior > 0.0f` を満たさず無効。 |

範囲チェック、clamp、警告、無効値専用の fallback はない。大文字小文字を区別する文字列比較も行わず、C ランタイムの `atof` で数値変換する。値を読むのは `Verifier::record_window` 内の関数 static 初期化時であり、最初にその宣言へ到達した後は同一プロセス内で再読込しない。したがって、実行中に環境変数を変更しても反映されない。

## 有効になる条件

- verify window のルーティング処理まで実行されること。Verifier の初期化は VRAM 専門家の profile/cache がない場合に失敗し、対応レイヤー形状などの検査も行う。
- `route_prior > 0.0f`、専門家数 `NE == 512`、top-k `K == 10`、および層ごとの在駐表 `hits_.d_res` が非 null であること。
- この環境変数を読むコードとカーネルは `verify.cpp` と `src/kernels/cuda/route_prior.cu` にあり、通常の verify window 経路に属する。CLI 引数や設定ファイルによる上書きはこの変数について実装されていない。

## 実行時の詳細

各レイヤーのルーター処理後、`route_prior_top10` は verify window の各トークン行について512個のロジットを調べる。在駐表の値が `>= 0` の専門家には選択スコアに `lambda` を加え、上位10個の ID を決め直す。同点の選択スコアでは小さい専門家 ID を優先する。

重みはボーナスを加えたスコアからは作らない。カーネルは元のロジットから得た確率を使い、選び直された10専門家の間で再正規化して `weights` に書く。その ID と重みは、この後の resident plan や doorbell 公開へ進む。さらに `STRATA_ROUTE_RESIDENT` が有効な場合は、その処理が `STRATA_ROUTE_PRIOR` の後に実行されるため、後段でルーティング結果が変更され得る。

この処理専用のログ出力や環境変数エラーはない。`docs/DETAILS.md` は `STRATA_ROUTE_PRIOR` について「adds speed, doubles the KL」と記しているが、この記述の箇所には測定条件が併記されていないため、速度や KL の定量値・一般的な効果としてはここでは扱わない。

## 根拠

- `src/core/verify.cpp:540-579` — Verifier 初期化で在駐表等の profile/cache 条件、形状条件を検査。
- `src/core/verify.cpp:1431-1468` — 通常のルーター処理後に値を初期化・判定し、512専門家・top-10・在駐表がある場合にカーネルを呼び出す。
- `src/kernels/cuda/route_prior.cu:29-68` — 在駐専門家への選択スコア加算、top-10 選択、元のロジット由来の重み再正規化、同点時の ID 優先。
- `src/kernels/cuda/route_prior.cu:73-77`、`include/strata/kernels/route_prior.hpp:9-13` — カーネル起動と API の選択・重み仕様。
- `src/core/verify.cpp:1469-1501` — `STRATA_ROUTE_RESIDENT` の後続処理と、結果を使う resident plan / doorbell 公開。
- `CMakeLists.txt:337-361` — CUDA カーネルライブラリのソースに `route_prior.cu` を含める。
- `docs/DETAILS.md:1661-1663` — 文書上の定性的な性能/KL 記述。該当箇所にはその主張の測定条件なし。
