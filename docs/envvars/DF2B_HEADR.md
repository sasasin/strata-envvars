# `DF2B_HEADR`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal の DFlash2 ベンチマーク `metal/tests/df2_bench.cpp` で、drafter head の `df2_mm` カーネル variant を選びます。値はカーネル名の一部となり、`R_S` の数値は dispatch の grid と threadgroup size にも使われます。Strata の通常の推論・サーバー実行コードには参照がなく、このベンチマークを実行するときだけの設定です。

## 値と判定

`std::getenv` で値を読み、未設定なら文字列 `4_8` を使います。設定値は `sscanf(s.c_str(), "%d_%d", &R, &S)` で整数 2 個として読みます。文字列全体の一致検査や戻り値の確認はなく、後続文字列は検査されません。

| 状態・値 | コード上の扱い |
|---|---|
| 未設定 | `4_8` を使う。 |
| 空文字 | 空文字をそのまま使う。`sscanf` が2整数を読み取れず、`R` と `S` は初期化されないまま後続処理に使われる。 |
| `4_8` など `%d_%d` に合う値 | 読めた整数を dispatch 計算に使う。 |
| `4_8tail` など整数2個の後に文字がある値 | 先頭の2整数を読み、末尾は無視する。 |
| 数値が不足する値（例: `4_x`） | `sscanf` の読み取り数を検査しないため、未読の整数は初期化されず使用される。 |
| `0_8` / `4_0` など | 範囲検証・clamp がない。dispatch の除算や threadgroup size の計算にそのまま渡る。 |

したがって、`R_S` 形式以外の値やゼロを安全に拒否・既定値へ戻す処理はありません。無効値に対する Strata 独自の警告やエラー処理もありません。

## 有効になる条件

- `metal/tests/df2_bench.cpp` の `df2_bench` を実行した場合に限ります。ソース内の参照はこのベンチマークだけです。
- `DF2B_ONLY=head` または全ステージ実行で head を組み立てるとき、`DF2B_KIND` が `mma` でなければ `DF2B_HEADR` が `mm(...)` に渡され、`df2_mm4_<値>` または `df2_mm_<値>` の pipeline 名になります。
- `DF2B_KIND=mma` の場合、head は `DF2B_HEADR` ではなく `DF2B_HEAD8` を使う `df2_mma8` 経路です。`DF2B_HEADR` は設定表示には残りますが、head の pipeline 選択には使われません。
- `DF2B_SKIP=mm` が設定されると `mm` lambda は行列 dispatch を追加せず戻るため、`DF2B_HEADR` による head dispatch は行われません。
- `DF2B_ONLY=ctx` / `block` / `soak` では head stage を実行しません。CLI の任意の `KERNEL_DIR` 引数はカーネルディレクトリだけを設定し、この変数との優先順位はありません。

## 実行時の詳細

値は `main()` の開始後、ベンチマーク設定を作る際に一度読み、`hvar` の文字列として保持されます。プロセス中の環境変更を再読込する仕組みはありません。`build_head()` は通常経路でこの文字列を `mm()` に渡し、`mm()` は `R` と `S` を再び `%d_%d` で読み、pipeline 名、`grid[0] = (m.rows + R * S - 1) / (R * S)`、`tg[0] = 32 * S` を設定します。head stage は `DF2B_ONLY=head` なら単独で、そうでなければ通常ベンチマークの一部として測定され、設定行には `head variant <hvar>` と表示されます。

値の形式や範囲をチェックするログ・エラー経路はありません。未定義の整数値が使われる不正形式やゼロを含む値では、dispatch の算術に不正な値が入ります。pipeline 名が存在しない場合など Metal 実行基盤側で起きる結果はこの Strata ソースからは規定できないため、ここでは記述しません。

## 根拠

- `metal/tests/df2_bench.cpp:1-9`: 対象が Metal DFlash2 のベンチマークであることと、環境変数の用途。
- `metal/tests/df2_bench.cpp:62-82`: `DF2B_HEADR` の読取、未設定時の既定値、および未検査の `%d_%d` 変換。
- `metal/tests/df2_bench.cpp:285-324`: variant を用いた pipeline 名と dispatch geometry の設定、`DF2B_SKIP=mm` による省略。
- `metal/tests/df2_bench.cpp:391-416`: `DF2B_KIND=mma` でない場合に `hvar` を head 行列処理へ渡すこと、および `mma` 経路との差。
- `metal/tests/df2_bench.cpp:441-465`: 設定値の表示と head stage の実行条件。
