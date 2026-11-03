# `STRATA_DS4_MARKS_INSIDE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。候補名の参照をソース全体で検索し、環境から読む実装は `src/dsv41/ds4_model.cu` の一箇所と確認した。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 エンジンの prompt 読み込みで、prompt 内の restore point（再利用用に状態を保存する位置）まで個別に読み進めず、複数の restore point を含む残りの prompt を一回の chunked run で読み、各点の状態を保存する経路を許可する。これは prompt の読み方と状態保存経路を選ぶスイッチであり、生成時の sampling 設定ではない。

CMake の `STRATA_BUILD_DSV41` が有効なときに追加される専用実行ファイル `strata-dsv41` のコードに実装されている。この CMake option は既定 OFF で、`STRATA_HIP_GFX906` の場合も target を追加しない。対象は選択された GPU runtime にリンクされる CUDA/HIP 系の DS4 target で、通常の `strata` target には組み込まれない（`CMakeLists.txt:931-945,958-962`）。環境読み取り箇所に OS 別の条件分岐はない。

## 値と判定

`Model::marks_inside()` で次の順に読み取る。文字列全体の厳密比較ではなく、`std::atoi()` の結果が 0 かどうかで判定する（`src/dsv41/ds4_model.cu:14927-14936`）。

| `STRATA_DS4_MARKS_INSIDE` | `DS4_MARKS_INSIDE` | 判定 |
|---|---|---|
| 未設定 | 未設定 | 有効（既定） |
| 設定あり | 参照しない | `atoi` の結果が 0 なら無効、非 0 なら有効 |
| 未設定 | 設定あり | 旧名を `atoi` で変換し、0 なら無効、非 0 なら有効 |

明示的な空文字は `atoi("") == 0` となるため無効で、主変数が空文字でも旧名への fallback はしない。`atoi` の通常の変換規則により、先頭空白と符号は数値変換に含まれ、数値部分の後ろの文字列は値判定に使われない。数字として読めない文字列も 0 となり無効。負の非ゼロ値は有効。数値としての上限・下限検査や clamp はない。

この判定を上書きする CLI 引数は `marks_inside()` にない。chunk サイズや prompt の読み込み条件は別途適用される。

## 有効になる条件

値判定が有効でも、次の条件を通らない場合はこの関数が false を返し、個別の restore point で区切る既存経路になる。

- DS4 model の `chunk` が正である。
- `rel` に restore point があり、個数が snapshot 枠に収まり（最大 7 点）、最初の点が読み込み区間の先頭より後、最後の点が末尾 token より前にある（`src/dsv41/ds4_model.cu:804,14927-14930`）。
- `ds4_main` 側で残り全体を読むケースである: `piece >= rest`、`rest <= m.feed_unit()`、restore point が残っており、`DS4_LAST_WINDOW` が未設定で、共有 prefix 用の停止条件 `start_kept` に該当しない（`src/dsv41/ds4_main.cpp:1223-1225,1233-1255`）。
- 内部追加コスト `p.inner_cost(n, rel)` が `p.chunk` 以下である（`src/dsv41/ds4_model.cu:14936`）。このコストは Yoco prompt skip により個別停止なら省けた行のうち、各区間で `keep` を超え、`kYocoMin` 以上となる分を合計する。該当する Yoco layer がない場合はコスト 0（`src/dsv41/ds4_model.cu:12864-12890`）。

したがって、chunk が無効なモデル状態、構造条件に合わない restore point、コストが chunk を超える状態では、変数が有効でも `feed_marks()` 経路は選ばれない。環境変数によるログや警告はこの判定箇所にはない。

## 実行時の詳細

`ds4_main.cpp` の `prompt_piece` が、上記の prompt 条件で全 restore point の相対位置を作って `m.marks_inside()` に問い合わせる。true の場合、その位置を `inner` に移し、読み込み長を残り全体にして `m.feed_marks()` を呼ぶ。成功時は今回の読み込みが通過した restore point をすべて処理済みにする（`src/dsv41/ds4_main.cpp:1240-1263`）。

`feed_marks()` は位置が読み込み区間内にあり、順序も正しいことを確認する。条件を満たさない場合は `feed_marks: a restore point that is not inside the read, or out of order` を返す。それ以外に chunked-run 条件を満たさない場合は通常の各点での読み込みに分け、満たす場合は `forward_chunks(..., &inner)` で一回の run にまとめる（`src/dsv41/ds4_model.cu:14894-14925`）。`forward_chunks()` 側でも snapshot 枠を超える点数を拒否する（`src/dsv41/ds4_model.cu:12895-12902`）。

環境値の評価は `marks_inside()` が構造条件を通過した最初の呼び出し時で、関数ローカル `static const bool` にプロセス内キャッシュされる。通常の設定ではモデルごと・request ごとの再評価ではなく、後から環境値を変更しても反映されない（`src/dsv41/ds4_model.cu:14927-14936`）。

処理失敗時、prompt handler は `ds4: <error>` を stderr に、`ERR...` と `DONE...` を stdout に出し、model state を reset する。GPU fatal text と判定された場合は通常のエラー出力より前に fatal 経路へ進む（`src/dsv41/ds4_main.cpp:1318-1340`）。この環境変数自体を示すログはない。

## 根拠

- 候補一覧には `STRATA_DS4_MARKS_INSIDE` が掲載されている（`docs/envvars/000_envvers.md:1064`）。同一覧の旧名候補 `DS4_MARKS_INSIDE` もあり（同 `:315`）、実装は主名と旧名の両方を明示的に読む。
- 実読み取り、優先順位、変換、cache、戻り条件: `src/dsv41/ds4_model.cu:14927-14936`。
- prompt 側の選択条件と呼び出し: `src/dsv41/ds4_main.cpp:1223-1263`。
- restore point の検証と fallback / chunked run: `src/dsv41/ds4_model.cu:12895-12902,14894-14925`。
- Yoco skip による追加コスト: `src/dsv41/ds4_model.cu:12864-12890`。
- 実行ファイルの CMake option と対象ソース: `CMakeLists.txt:931-945,958-962`。
