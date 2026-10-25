# `STRATA_ROPE_TABLE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

RoPE の回転角度を、セッションがホストで float64 で組み立てて VRAM に上げた cos/sin テーブルから読むようにする、解析式（analytic）経路の opt-in 切り替えです。

Strata の rope には二つの形があります。

- **テーブル経路（既定の decode 経路、indexer の pooled key）**: `build_rope_table` がホストで float64 で組み立てた表を読み、kernel は純粋な回転だけを行う（`src/kernels/cuda/rope.cu:48-59`, `src/core/layer.cpp:834-847`）。この経路は環境変数を読まない。
- **解析経路（`--native-rope` の native kernel、native QSA indexer、prefill の prompt path）**: `pos * powf(theta_scale, pair)` を device で計算し、`cosf`/`sinf`（`--use_fast_math` 下）で角度を作る。

`STRATA_ROPE_TABLE=1` はこの解析経路を、テーブルが効く範囲でテーブル読み（`rope_tab_cs`）に切り替えます。切り替えは kernel のテンプレート引数 `TAB` の選択として行われ、`TAB=false` の instantiation は「テーブル読みが存在しない」0.1.31 のコードそのものです（`src/kernels/cuda/native_rope.cu:42-45`, `src/prefill/kernels.cu:1625-1628`）。

実装は `src/kernels/cuda/native_rope.cu`（CUDA と HIP で共有される translation unit、`CMakeLists.txt:360,429`）と、その SYCL 複製 `sycl/src/kernels/cuda/native_rope.dp.cpp` にあります。環境変数を読む箇所はこの両ファイルの `rope_table_enabled()` だけで、Python サーバー・セットアップ・CPU 実装にはありません。

## 値と判定

文字列全体は parse しません。`std::getenv` の結果の先頭文字 `e[0]` だけを `'1'` と比較します。

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定されているが先頭文字は `\0`） |
| 先頭文字が `1` | 有効。例: `1`, `10`, `1anything` |
| それ以外 | 無効。例: `0`, `true`, `yes`, `on`, ` 1`（先頭が空白） |

数値変換、大文字小文字、後続文字の検査はありません。CUDA/HIP/SYCL で判定規則の差はありません。

読み取りは `rope_table_enabled()` 内の `static const bool` に一度だけキャッシュされます（`src/kernels/cuda/native_rope.cu:152-158`）。初回判定はプロセス起動時ではなく、`rope_table_for()` が最初に呼ばれたとき、つまり最初の rope kernel launch の host 側です。その後の環境変更は反映されません。

## 有効になる条件

判定が有効でも、次のすべてが揃わなければテーブル読みは使われません。

1. **テーブルが登録されていること**。登録は `qsa_state_init` だけが行う（`src/core/layer.cpp:838-847`）。条件は `share_rope == nullptr`（他の状態の表を借りている状態は登録しない）かつ `s.n_rot == 64`。したがって QSA 層を持たないモデル、または `share_rope` で表を共有している状態では、`rope_table_for()` は常に空の `RopeTab` を返し、環境変数は効かない。
2. **スケーリングが一致すること**。`rope_table_for()` は登録時の `RopeScaling` と呼び出し側の `scaling` を `same_scaling()` で比べ、違えば空を返す（`src/kernels/cuda/native_rope.cu:146-150,168-172`）。
3. **現在の device に登録された表であること**。登録は device ごと（`rope_tab[kMropeDevices]`、`kMropeDevices = 64`）。layer split で複数 device にまたぐ場合は device ごとに別の表が効く。同じ device では後勝ち（`rope_table_set` が上書き）。`session_release` で表のメモリを解放するときは `rope_table_release()` が全 device の該当エントリを消す（`src/kernels/cuda/native_rope.cu:160-167`, `src/core/session.cpp:132-138`）。
4. **解析経路が実際に走ること**。`native_rope_apply` は `native_rope_enabled()` のときだけ呼ばれる（`src/core/layer.cpp:1031`）。これは CLI の `--native-rope`（`src/program/generate.cpp:1871,3057`）で、`--native` のまとめ設定でも立つ（`src/program/generate.cpp:2505`）。`--native-rope` なしの decode 経路は `rope_neox_apply`（テーブル読み）なので、この環境変数は影響しない。同様に indexer は `native_qsa_indexer_enabled()` のときだけ native 経路（`src/core/layer.cpp:1101-1107`）。
5. **位置がテーブルの範囲内であること**。`rope_tab_cs()` は `p < 0` または `p >= t.max_pos`（`max_pos = max_cells`）なら false を返し、その pair だけ解析式に fallback する（`include/strata/kernels/mrope.hpp:56-61`）。テーブルは pair 0..31（`n_rot/2`）分しか持たない。

## 実行時の詳細

- host 側は launch 直前に `rope_table_for(scaling)` を呼び、結果が非空なら `TAB=true`、空なら `TAB=false` の kernel を launch する。分岐は次の箇所にある。
  - decode の native rope: `src/kernels/cuda/native_rope.cu:207-215`
  - 融合 norm+rope（`native_qsa_rms_norm_rope`）: `src/kernels/cuda/native_rope.cu:233-241`
  - prefill の prompt path（`strata::prefill::rope`）: `src/prefill/kernels.cu:2191-2201`
  - native QSA indexer の append / append_first / append_blocks: `src/kernels/cuda/native_qsa_indexer.cu:255-263,286-300`
- kernel 内では `TAB && rope_tab_cs(...)` が true のときテーブルの cos/sin を使い、false のとき従来どおり `mrope_pos()` と `powf`/`rope_scaled_angle` で角度を作る（`src/kernels/cuda/native_rope.cu:61-64,112-115`, `src/prefill/kernels.cu:1638-1641`, `src/kernels/cuda/native_qsa_indexer.cu:99-102,133-136`）。
- 角度の参照位置は IMRoPE のセクション位置（`mrope_pos(mtab, pos, pair)`）で、テーブルは `pair`（0..31）番目のエントリを使う。
- テーブルは `RopeTab` 構造体として kernel 引数で渡される。CUDA graph は引数を capture 時に焼き込むため、判定は capture 前に確定している必要がある。設計注釈は「session init で設定し、graph capture 前」と述べる（`src/kernels/cuda/native_rope.cu:140`）。
- SYCL 複製では `rope_tab_cs` の `__ldg` が単なる dereference に変換されている（`sycl/include/strata/kernels/mrope.hpp:54-62`, DPCT1098 注釈）。読み取る値は同じだが、CUDA/HIP 版と同一命令ではない。

## 観測できる結果

この環境変数はログ・警告・エラーを出さない。stdout/stderr には何も出ず、観測できる変化は生成結果だけである。

- 有効時、解析経路の角度がテーブルの float64 由来の値（float32 に丸められたもの）になる。ソースの注釈は「テーブルの角度は fast-math のものと末尾ビット只差で、outputs が動く」と書く（`src/kernels/cuda/native_rope.cu:151`）。
- 注釈は `--use_fast_math` 下で 32K で 0.0014 rad、262K で約 0.02 rad の差、そして prompt path（precise libm）と decode（fast-math）が互いに食い違うと述べる（`include/strata/kernels/mrope.hpp:32-34`）。これは測定環境・回数が示されていない設計注釈であり、確認済みの数値として扱わない。
- 両経路の不一致は parity test の根拠にもなっている。`rope_parity` の check 5 はテーブル経路と native 経路の一致を、fast-math の range reduction で ~1e-4 相当の誤差が出ることを踏まえ、行の大きさを基準にした 3e-3 の tolerance で検査する（`src/kernels/rope_parity.cpp:348-354`）。テストは実装の根拠にしない。

## 相互作用・制限

- `docs/DETAILS.md` と README にはこの環境変数の記載がない。コードとコメントにのみ現れる opt-in フックである。
- セッションファイルの config fingerprint は rope の解決済み設定（type、freq_base、factor、freq_scale、orig_ctx、YaRN の knobs）と `native_rope` switch を含むが、この環境変数を含まない（`src/core/conversation_file.cpp:878-900`, `src/program/generate.cpp:7793-7804`）。同じ設定で ON/OFF を切り替えた実行は fingerprint 上区別されず、保存済みセッションは環境変数の違いを拒否しない。
- 値が有効でも、上記「有効になる条件」の 1（QSA 層と `n_rot == 64`）が満たされないモデルでは一切効かない。この環境変数は Strata の同梱ツール専用のフックではなく、実行ファイルに組み込まれる分岐だが、対象は解析経路の rope kernel に限定される。

## 根拠

- 読み取りと判定: `src/kernels/cuda/native_rope.cu:151-158`（SYCL 複製 `sycl/src/kernels/cuda/native_rope.dp.cpp:205-212`）
- 参照と fallback: `src/kernels/cuda/native_rope.cu:146-150,160-172`, `include/strata/kernels/mrope.hpp:30-46,56-61`
- 登録条件: `src/core/layer.cpp:838-847`（SYCL 複製 `sycl/src/core/layer.cpp:952-965`）
- 解放: `src/core/session.cpp:132-138`
- kernel 分岐: `src/kernels/cuda/native_rope.cu:45-68,70-125,207-215,233-241`, `src/prefill/kernels.cu:1628-1641,2191-2201`, `src/kernels/cuda/native_qsa_indexer.cu:99-102,133-136,255-263,286-300`
- 経路選択（CLI）: `src/program/generate.cpp:1871,2505,3057`, `src/core/layer.cpp:1031,1101-1107`
- 設計注釈の差: `include/strata/kernels/mrope.hpp:32-34`, `src/kernels/cuda/native_rope.cu:151`
- fingerprint: `src/core/conversation_file.cpp:878-900`, `src/program/generate.cpp:7793-7804`
