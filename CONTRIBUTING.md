# Working together

## Git flow

1. Pull the latest `main`: `git checkout main && git pull`
2. Make a branch named after you and the task: `git checkout -b yogi/ward-geojson`
3. Commit small steps with clear messages.
4. Push and open a pull request into `main`: `git push -u origin yogi/ward-geojson`
5. Alpharnog reviews and merges. Don't push straight to `main`.

## Rules that keep us unblocked

- Talk through `docs/contracts.md`. If you need a new field, change the contract in its
  own small pull request first, so everyone sees it.
- Build against fake data when the real piece isn't ready. The mock LLM and the sample
  files exist for exactly this.
- Every real number in `backend/data/` carries its source and year in `source_note`.
- Backend changes come with a test in `backend/tests/` when they change behaviour.
- Everyone must be able to explain their own code in the viva.

## Where to start, per person

- **YOGI (world and data):** convert the GBA 2025 ward KML to GeoJSON, choose 3 to 5
  study wards, and replace `backend/data/wards.sample.json` with sourced numbers. Then
  tune the rules in `WorldEngine.step` (`backend/namma/world.py`).
- **USMAN (dashboard):** draw real ward polygons from YOGI's GeoJSON instead of circles,
  then build the replay player on top of the files in `backend/runs/`.
- **BABU (research and personas):** write the literature survey and synopsis, then
  replace `backend/data/citizens.sample.json` with 25 personas built from ward
  demographics, and write the 20 God Mode test commands.
