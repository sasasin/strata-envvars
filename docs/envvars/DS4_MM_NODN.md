# `DS4_MM_NODN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `main...origin/main` で、未コミット変更は表示されなかった。

## 役割

DeepSeek 4.1 の IQ MoE set-down 処理で、Metal down-matrix カーネルの dispatch を省略する診断用スイッチです。設定されると `mm_set(false, ...)` は down dispatch を実行せず `true` を返します。呼び出し元は Metal 処理が完了したものとして扱うため、後続の CUDA 互換 down カーネルにもフォールバックしません。通常利用時に有効化する設定ではなく、down 出力を生成しない経路になります。

## 値と判定

| 状態 | 判定 | 結果 |
|---|---|---|
| 未設定 | `std::getenv(...) == nullptr` | down dispatch を続行する |
| 空文字を設定 | 戻り値は非 null | down dispatch と結果コピーを省略し、成功を返す |
| 任意の非空文字列 | 戻り値は非 null | 空文字と同じく省略し、成功を返す |

`0` / `false` などの文字列比較、数値変換、範囲検査はありません。設定値の真偽ではなく、環境変数が存在するかだけを調べます。値は `mm_set` の呼び出しごとに読むため、この判定箇所に static cache はありません。CLI 引数や別の環境変数による優先順位・上書きも実装されていません。

## 有効になる条件

この読み取りは Apple/macOS 専用の Metal エンジンに限られます。`metal/CMakeLists.txt` は Apple 以外で Metal build を拒否し、`src/dsv41/ds4_iq.cu` の Metal 呼び出しは `STRATA_METAL` 定義時だけコンパイルされます。CUDA / HIP / SYCL の通常ビルドではこの環境変数を読む箇所はありません。

さらに、DeepSeek 4.1 IQ MoE の set-down 経路で `set_down()` が呼ばれ、`a.hbounds != nullptr` のときに Metal `iq_set_dn()` が呼ばれる必要があります。`mm_set` は `n_exp <= 0` または `total_rows <= 0` なら環境変数を調べる前に成功を返します。IQ type、次元、stride 等の条件不成立や Metal 準備失敗時は `false` を返し、呼び出し元は互換カーネル側の処理へ進みます。タイル数が 0 の場合も環境変数の判定前に成功を返します。

## 実行時の詳細

`iq_set_dn()` は `mm_set(false, ...)` を呼びます。この `false` により `type` として down の量子化 type `td` が選ばれ、最後の分岐で `DS4_MM_NODN` が検査されます（gate/up 側では同じ式が `DS4_MM_NOGU` を選びます）。判定はタイル、Metal pipeline、dispatch 引数を用意した後、`g_cx->run({d})` の直前です。

変数が設定されている場合、Strata は tile buffer `bt` を解放して `true` を返します。そのため down の Metal dispatch と、その直後に行われる `g_mm_ys` から `yout` への `ds4_copy4` も実行されません。`set_down()` は Metal 関数が `true` を返すと直ちに成功扱いで戻り、通常の tq / CUDA 互換 down カーネルを起動しません。したがって、この経路では Strata による down 出力の計算・コピーが省かれます。省略時の出力内容や、それが後段の生成結果に及ぼす具体的な値は、この分岐だけからは確定できません。

この環境変数専用のログ、警告、エラー、終了処理はありません。設定値が無効として拒否されることもありません。

## 根拠

- `metal/src/engine/ds4_finish.cpp:2476-2484,2489-2495`: `mm_set` の前提条件、Metal 準備とタイル数 0 の早期 return。
- `metal/src/engine/ds4_finish.cpp:2614-2634`: down 側の診断分岐、`DS4_MM_NODN` の設定有無判定、tile buffer 解放後の成功 return、通常 dispatch と down 結果コピー。
- `metal/src/engine/ds4_finish.cpp:2641-2643`: `iq_set_dn()` が `mm_set(false, ...)` を呼ぶ。
- `src/dsv41/ds4_iq.cu:1604-1620`: `STRATA_METAL` 下で `hbounds` があると Metal 関数を呼び、その成功時に通常の down カーネルへ進まず戻る。
- `metal/CMakeLists.txt:1-2,14-18,132-169`: Metal build は macOS 専用であり、DeepSeek engine の DS4 target に `STRATA_METAL=1` を定義する。
- 候補一覧は `docs/envvars/000_envvers.md:234` に記載。`DS4_MM_NODN` のコード参照は上記の動的な名前選択を含め `metal/src/engine/ds4_finish.cpp:2616` のみ。`docs/DETAILS.md` と関連する `docs/DEEPSEEK_MAC.md` / `docs/DEEPSEEK41.md` / `docs/MAC.md` に、この変数の説明は見つからなかった。
