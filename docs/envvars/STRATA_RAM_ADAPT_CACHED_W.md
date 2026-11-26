# `STRATA_RAM_ADAPT_CACHED_W`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_RAM_ADAPT2` の resident RAM 適応処理で、候補 expert がファイル tier の page cache にある場合に、RAM へ昇格させる候補スコアへ掛ける重みを指定する。cold file tier の候補にはこの重みを掛けず、RAM や GPU の配置自体、ファイルキャッシュ、読み取り方法を直接変更する変数ではない。候補の順位や交換候補としての採否を変えうるが、モデルの routing や重みは変えない（`engine/src/program/generate.cpp:22862-22909`）。

## 値と判定

`--serve` の初期化時、`RamAdapt2` の `cached_w` に既定値 `0.15f` を置き、環境変数が設定されていれば `std::atof` で先頭の数値部分を `double` に変換し、`[0.0, 1.0]` に `std::clamp` してから `float` にする。文字列全体の妥当性検査やエラー報告はない（`engine/src/program/generate.cpp:12332-12348`）。

| 条件 | unset | 有効になる値の例 | 変換後の値・無効値の例 |
| --- | --- | --- | --- |
| serve 初期化時 | `0.15` | `0.4`, `1`, `0.4tail` | `0` は `0`; `2` は `1`; `-0.2` は `0`; `0.4tail` は先頭数値を使い `0.4` |
| 空文字・数値に変換できない文字列 | — | — | `""` と `n/a` は `atof` が `0` を返すため `0` |

`atof` が認識する数値の後ろは検証されず、先頭空白も数値変換に従って扱われる。したがって、例えば `0.4tail` は拒否されず `0.4` になる。未設定だけが既定値を保ち、明示的な空文字は既定値ではなく `0` になる。範囲外の有限値は clamp される。数値変換結果が NaN となる文字列を与えた場合は有限値として検証されず、`std::clamp` の比較を通過して NaN が残る可能性がある（同 `generate.cpp:12346`）。

## 有効になる条件

- `--serve` のコード経路で読み込まれる。値の読み取りだけなら関連する適応スイッチが OFF でも行うが、候補計算に使うには `STRATA_RAM_ADAPT2` が `atoi` で非 0、かつ `STRATA_RAM_ADAPT` が `atoi` 後に正である必要がある（`engine/src/program/generate.cpp:12302-12348`, `22843-22849`）。
- 実際の処理には、先頭 decode window 以降、routing 使用量があり、適応 round が未処理で、非同期 job がないか idle、resident RAM copy が準備済み、単一 GPU、peer device なし、remote expert optimization なし、`--batch` なし、という条件も必要（`engine/src/program/generate.cpp:22847-22849`）。候補自体も GPU 外かつ RAM copy 外でなければならない（同 `generate.cpp:22868-22873`）。
- `FileExpertSource::tier_of()` が page-cache tier (`1`) と判定した候補に限り重みを使う。これは Linux では cached pages の確認結果により `1` または cold file tier `2` を返し、Linux 以外では常に `2` を返す実装である（`engine/src/core/expert_source.cpp:5108-5119`）。よって Linux 以外ではこの変数の値による候補スコア調整は起きない。
- `STRATA_RAM_ADAPT_PROMPT_W` は prompt routing の seed、`STRATA_RAM_ADAPT_PER_LAYER` は layer あたりの対数、`STRATA_RAM_ADAPT_SKIP_TOP` は候補除外数を別途決める（`engine/src/program/generate.cpp:12345-12348`, `16056-16067`, `22877-22891`）。`STRATA_RAM_ADAPT_QUEUE` は読み取り queue の上限となり、満杯なら `ram_stage()` が候補を queue に入れない（`engine/src/core/expert_source.cpp:5009-5030`）。これらを含め、`STRATA_RAM_ADAPT_CACHED_W` を CLI 引数が上書きする実装はない。

## 実行時の詳細

変数は serve 経路の `RamAdapt2` 初期化ブロックで一度読み、値をその server 実行中の struct に保持する。リクエストごと・window ごとに環境から読み直す処理や、後から環境を変更した値を反映する処理はない（`engine/src/program/generate.cpp:12332-12348`）。

適応処理は window 境界で完了済みの RAM 昇格を install し、各 layer の routing count と prompt seed から候補を作る。GPU 外・RAM 外の incoming 候補のうち、既に RAM queue にあるものは除外し、それ以外は `tier_of(...) == 1` の場合だけ `cached_w` をスコアに掛けて outgoing 候補との差を評価する。正の候補差が少なくとも `1.0` の組を gain 順に stage し、上限 `STRATA_RAM_ADAPT` 件まで読み取り queue へ送る（`engine/src/program/generate.cpp:22856-22917`）。Linux では page-cache にある候補を cold file read 候補より低く評価しうる重みであり、`0` ならその候補の incoming score を 0 にする。`1` ならその重み付けをしない。これは推定スコアに対する制御で、実際にキャッシュ hit することを保証しない。

## ログと測定値

この変数専用の有効・無効・値表示ログや失敗メッセージはない。`STRATA_RAM_ADAPT2` が有効なら request の累積値として promotions read / installed / skipped を stderr に出すが、この表示に `cached_w` の値は含まれない（`engine/src/program/generate.cpp:23801-23805`）。資料にこの変数自体の測定値は見つからなかったため記載しない。

## 根拠

- `engine/src/program/generate.cpp:12332-12348` — struct の既定値、環境変数の読み取りと変換。
- `engine/src/program/generate.cpp:22843-22917` — RAM 適応の条件、候補選定・重み適用・stage。
- `engine/src/core/expert_source.cpp:5009-5030` — queue 上限と stage 受付。
- `engine/src/core/expert_source.cpp:5108-5119` — Linux page-cache tier の判定と他 OS の分岐。
- `engine/src/program/generate.cpp:23801-23805` — 関連する累積ログ。
- `docs/DETAILS.md:261-282` — resident RAM mode と既存 `STRATA_RAM_ADAPT` の概要。対象重みの具体的な説明や測定値はない。
