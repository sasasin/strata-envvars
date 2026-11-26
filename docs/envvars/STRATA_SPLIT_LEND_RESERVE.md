# `STRATA_SPLIT_LEND_RESERVE`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（`2026-11-26` 時点）。

## 役割

複数 GPU の layer split で prompt path 用の stage lend region があり、RAM 予算つきの expert copy を作るとき、各 region のうち何 slot 分を expert profile 順の complement より先に RAM 予算へ確保するかを指定する。`0` は complement を先に埋め、`1`〜`99` は各 region の高い slot 側から指定割合の slot を先取りし、`100`・`full`・未設定などは全 region を先取りする。これは RAM 内に置く expert の優先順位を変える設定で、prompt path に lend する slot やモデルの expert の選択自体は変更しない。読み取りと先取り計算は `FileExpertSource::pin_cache_complement` にある（`engine/src/core/expert_source.cpp:4130-4173`）。

## 値と判定

`std::getenv` の結果を `split_lend_reserve_percent` に渡す。未設定または空文字は 100。空でない値はまず文字列全体が大文字小文字を区別して `full` と一致するか確認し、次に `auto` 以外を `std::strtol(..., 10)` で変換する。変換が少なくとも 1 文字進み、終端まで読み切り、結果が 0〜100 の場合だけ受理する。したがって先頭の空白と `+` は `strtol` が許すため受理されるが、末尾の空白や余分な文字は無効。数値の overflow も範囲外結果となり無効。大文字小文字を正規化しない。無効値は 100 に fallback する（`engine/src/core/expert_source.cpp:357-373`）。

| 条件 | unset / 空文字 | 設定時に有効 | 無効または既定値になる例 |
|---|---|---|---|
| stage lend region があり、RAM budget が正 | `100` | `0`〜`100` の base-10 整数。`full` は `100`。`auto` は既定の `100` | `true`, `false`, `FULL`, `101`, `-1`, `1x`, `1 ` は `100`。`+1` と先頭空白つき ` 1` は `strtol` の規則で `1` |
| stage lend region がない、または RAM budget が 0 | 値を読まない／本変数の判定をしない | 適用なし | 適用なし |

整数の 0 は受理されるため、`-0` も変換結果が 0 となり有効。受理後は各 stage の region ごとに `ceil(region.size() * percent / 100)` 個を先頭から取り、region は高い slot 順なのでその slot 群の expert bytes を complement より先に予算へ計上する。端数は切り上げられ、割合は byte 数ではなく region の pair 数に対して適用される（`engine/src/core/expert_source.cpp:4150-4169`）。

## 有効になる条件

- `generate` の resident CPU expert 経路で `pin_cache_complement` が呼ばれること（`engine/src/program/generate.cpp:11908-11910, 12078-12080`）。
- 分割 GPU で prompt borrowing が使われ、`pf_borrow`、`d_res`、正の `o.prefill_chunk`、`multi_gpu`、非空の `stages` がそろって stage lend region が構成されること。GPU ごとに lend 可能な slot がなければ region は追加されない（`engine/src/program/generate.cpp:11950-11966, 12012-12041`）。
- `pin_cache_complement` に正の RAM budget が渡ること。通常の budget 処理内でのみ本変数が読まれる（`engine/src/core/expert_source.cpp:4066-4068, 4141-4147`）。soft resident の再試行では `kResidentWhatFits` の budget を使って同じ判定を行う（`engine/src/program/generate.cpp:12091-12099`）。
- stage region 内で先取りされなかった slot も、complement を詰めた後に予算が残れば RAM copy に追加される。先取り指定は領域全体の最終的な収容率を固定しない（`engine/src/core/expert_source.cpp:4300-4324`）。
- 値の判定に OS/backend/build macro による別ルールはない。少なくとも、この設定を読むコードに OS・backend 分岐はない。Windows では別の WDDM 制約が budget を clamp する場合があるが、本変数の値規則は変わらない（`engine/src/core/expert_source.cpp:4090-4128`）。

## 実行時の詳細

`pin_cache_complement` の呼び出し時に、stage lend region が非空なら環境を読み、budget 分岐内で割合を一度判定する。関数内 static cache はなく、実行中に環境を書き換えた場合の再反映は通常の初回 startup 判定後には起きない。soft resident の失敗後に `pin_cache_complement` が再度呼ばれる経路では、その再呼び出し時にもう一度読む（`engine/src/core/expert_source.cpp:4003-4008, 4141-4147`; `engine/src/program/generate.cpp:12091-12099`）。

先取り分の bytes を RAM 予算から控除して complement の上限を求め、profile rank の expert をその残りへ配置する。その後、先取り prefix を先に、各 region の残りを次に追加する。予算に入らなかった expert は mapped file fallback のままになる（`engine/src/core/expert_source.cpp:4148-4185, 4300-4324`）。`what_fits` の soft mode で complement に 1 件も入らず、かつ lend reservation が 0 の場合は `pin_cache_complement` が `FileExpertSource: available memory cannot hold any expert of the complement` で失敗する。呼び出し元は resident soft 経路で再試行し、再試行も失敗なら元と再試行のエラーをまとめて返す経路に進む（`engine/src/core/expert_source.cpp:4187-4190`; `engine/src/program/generate.cpp:12091-12106`）。

## ログと測定値

判定結果が 100% 以外のときだけ stderr に次の形式で出る。100%（未設定・空文字・`full`・`auto`・無効値を含む）ではこの行を抑制する（`engine/src/core/expert_source.cpp:4143-4146`）。

```text
FileExpertSource: the stage lend reservation takes N% of the lend regions before the complement is filled: REASON
```

`N` は判定された割合。`REASON` は受理された数値なら `STRATA_SPLIT_LEND_RESERVE=<入力値>`、fallback なら `the whole reservation (#6583), the default`。無効値について専用 warning や終了はなく、100% に fallback する。後続の RAM 不足や soft fallback は別の失敗・警告経路である（`engine/src/core/expert_source.cpp:371-372, 4187-4190`; `engine/src/program/generate.cpp:12091-12106`）。

`docs/DETAILS.md:288` は `1`〜`99` を borrowed slots の bytes の割合として説明するが、現行コードは各 stage の region 内で割合分の **pair 数を切り上げて**先取りし、その pair の bytes を加算する。region 内の expert byte size が一様でない場合、先取り bytes の割合と指定値は一致しない。コードと資料のこの説明差は、資料の記述だけでは解消できないためここではコード上の実装を記した。資料には RAM-tight な 2 GPU split の測定として、RTX 4090 + RTX 3090 と 7 GB/s NVMe の例で decode 82.6 から 90.1 tok/s（最大 +9%）および 18K-token cold prompt reading 約 5% のコスト、2 x RTX A6000 で decode +5.5% および reservation 100% から 0% で cold prompt reading -17% と記載されている。これらは資料・ソースコメントの報告値で、ここで再測定した値ではない（`docs/DETAILS.md:288`; `engine/src/core/expert_source.cpp:4134-4138`）。

## 根拠

- `engine/src/core/expert_source.cpp:357-373` — 値の parse、fallback、理由文字列。
- `engine/src/core/expert_source.cpp:4066-4068, 4139-4173` — budget 条件、実読み取り、region ごとの先取りと complement budget。
- `engine/src/core/expert_source.cpp:4300-4324` — 先取り prefix と残り lend region の配置。
- `engine/src/program/generate.cpp:11908-11910, 11950-11966, 12012-12041, 12078-12099` — resident expert 経路と split lend region の生成・呼び出し。
- `engine/src/core/expert_source.cpp:4187-4190`; `engine/src/program/generate.cpp:12091-12106` — soft mode の失敗と再試行。
- `docs/DETAILS.md:288`; `engine/src/core/expert_source.cpp:4134-4138` — 資料に記載された測定報告と仕様説明。
